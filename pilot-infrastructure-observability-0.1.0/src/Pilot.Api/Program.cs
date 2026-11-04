using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Pilot;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls("http://127.0.0.1:5080");
builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = 64 * 1024);
var key = Environment.GetEnvironmentVariable("PILOT_API_KEY");
if (string.IsNullOrWhiteSpace(key) || key.Length < 24)
    throw new InvalidOperationException("Set PILOT_API_KEY to a random value of at least 24 characters.");
var store = new PilotStore(Environment.GetEnvironmentVariable("PILOT_DATA_DIR") ?? Path.Combine(builder.Environment.ContentRootPath, "data"));
builder.Services.AddSingleton(store);
var app = builder.Build();
app.Use(async (ctx, next) => {
    ctx.Response.Headers["X-Content-Type-Options"] = "nosniff";
    ctx.Response.Headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'";
    if (ctx.Request.Path.StartsWithSegments("/api")) {
        ctx.Response.Headers.CacheControl = "no-store";
        var supplied = ctx.Request.Headers["X-Pilot-Key"].ToString();
        if (!CryptographicOperations.FixedTimeEquals(SHA256.HashData(Encoding.UTF8.GetBytes(supplied)), SHA256.HashData(Encoding.UTF8.GetBytes(key)))) {
            ctx.Response.StatusCode = 401; return;
        }
    }
    try { await next(); }
    catch (ArgumentException e) { ctx.Response.StatusCode = 400; await ctx.Response.WriteAsJsonAsync(new { error = e.Message }); }
});
app.UseDefaultFiles(); app.UseStaticFiles();
app.MapGet("/healthz", () => Results.Ok(new { status = "ready", version = "0.1.0" }));
app.MapGet("/api/v1/machines", () => store.View());
app.MapGet("/api/v1/events", () => store.Events());
app.MapPost("/api/v1/observations", async (Observation input) => {
    if (input.SchemaVersion != 1) throw new ArgumentException("schemaVersion must be 1");
    if (input.Id is null || !Regex.IsMatch(input.Id, "^[a-zA-Z0-9_-]{1,100}$")) throw new ArgumentException("Invalid observation id");
    if (input.MachineId is null || !Regex.IsMatch(input.MachineId, "^[a-zA-Z0-9_-]{1,100}$")) throw new ArgumentException("Invalid machine id");
    if (string.IsNullOrWhiteSpace(input.Name) || input.Name.Length > 100 || string.IsNullOrWhiteSpace(input.Os) || input.Os.Length > 100) throw new ArgumentException("Name and OS are required (max 100 characters)");
    var now = DateTimeOffset.UtcNow;
    if (input.ObservedAt > now.AddMinutes(2) || input.ObservedAt < now.AddHours(-24)) throw new ArgumentException("Timestamp must be within the last 24 hours and at most 2 minutes ahead");
    if (input.Metrics is null || input.Metrics.Count is < 1 or > 3) throw new ArgumentException("Supply 1 to 3 metrics");
    foreach (var (name, value) in input.Metrics) {
        if (!new[] { "cpuPercent", "memoryPercent", "diskPercent" }.Contains(name) || !double.IsFinite(value) || value < 0 || value > 100) throw new ArgumentException("Supported metrics: cpuPercent, memoryPercent, diskPercent, each 0–100");
    }
    var result = await store.Ingest(input, now);
    return result == "conflict" ? Results.Conflict(new { error = "Observation id already used with different content" }) : Results.Ok(new { status = result });
});
app.Run();
