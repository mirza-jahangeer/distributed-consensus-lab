using System.Text.Json;
namespace Pilot;
public sealed record Observation(int SchemaVersion, string Id, string MachineId, string Name, string Os, DateTimeOffset ObservedAt, Dictionary<string, double> Metrics);
public sealed record Machine(string Id, string Name, string Os, DateTimeOffset ObservedAt, DateTimeOffset ReceivedAt, Dictionary<string, double> Metrics);
public sealed record Evidence(string Id, DateTimeOffset At, string MachineId, string Kind, string Summary, string ObservationId);
public sealed record Snapshot(List<Machine> Machines, List<Evidence> Events, List<Observation> Recent);
public sealed class PilotStore {
    private readonly SemaphoreSlim gate = new(1, 1);
    private readonly string path;
    private Snapshot state;
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);
    public PilotStore(string directory) {
        Directory.CreateDirectory(directory); path = Path.Combine(directory, "pilot.json");
        // Fail visibly on corrupt storage; never silently replace inventory.
        state = File.Exists(path) ? JsonSerializer.Deserialize<Snapshot>(File.ReadAllText(path), Json) ?? throw new InvalidDataException("Invalid snapshot") : new([], [], []);
    }
    public static string Health(Machine m, DateTimeOffset now) {
        if (now - m.ObservedAt > TimeSpan.FromMinutes(2)) return "stale";
        // Missing coverage must never be presented as fully healthy.
        if (m.Metrics.Values.Any(v => v >= 90)) return "critical";
        if (m.Metrics.Values.Any(v => v >= 80)) return "warning";
        return m.Metrics.Count < 3 ? "unknown" : "healthy";
    }
    public object View() {
        gate.Wait(); try {
            var now = DateTimeOffset.UtcNow;
            return state.Machines.OrderBy(m => m.Name).Select(m => new { machine = m, health = Health(m, now), missingMetrics = new[] {"cpuPercent", "memoryPercent", "diskPercent"}.Except(m.Metrics.Keys).ToArray() }).ToArray();
        } finally { gate.Release(); }
    }
    public Evidence[] Events() { gate.Wait(); try { return state.Events.AsEnumerable().Reverse().Take(200).ToArray(); } finally { gate.Release(); } }
    public async Task<string> Ingest(Observation input, DateTimeOffset now) {
        await gate.WaitAsync();
        try {
            var duplicate = state.Recent.FirstOrDefault(o => o.Id == input.Id);
            if (duplicate is not null) return Equivalent(duplicate, input) ? "duplicate" : "conflict";
            var old = state.Machines.FirstOrDefault(m => m.Id == input.MachineId);
            if (old is not null && input.ObservedAt <= old.ObservedAt) return "outOfOrder";
            if (old is null && state.Machines.Count >= 100) throw new ArgumentException("Pilot limit: 100 machines");
            var machine = new Machine(input.MachineId, input.Name, input.Os, input.ObservedAt, now, new(input.Metrics));
            var machines = state.Machines.Where(m => m.Id != machine.Id).Append(machine).ToList();
            var events = new List<Evidence>(state.Events);
            var current = Health(machine, now);
            if (old is null || Health(old, now) != current) events.Add(new(Guid.NewGuid().ToString("N"), now, machine.Id, old is null ? "discovered" : "healthChanged", old is null ? $"Discovered {machine.Name}; {current}" : $"Health: {Health(old, now)} → {current}", input.Id));
            var next = new Snapshot(machines, events.TakeLast(2000).ToList(), state.Recent.Append(input).TakeLast(1000).ToList());
            var temporary = path + ".tmp";
            await File.WriteAllTextAsync(temporary, JsonSerializer.Serialize(next, Json));
            File.Move(temporary, path, true);
            state = next; return "accepted";
        } finally { gate.Release(); }
    }
    private static bool Equivalent(Observation a, Observation b) => a.SchemaVersion == b.SchemaVersion && a.MachineId == b.MachineId && a.Name == b.Name && a.Os == b.Os && a.ObservedAt == b.ObservedAt && a.Metrics.Count == b.Metrics.Count && a.Metrics.All(kv => b.Metrics.TryGetValue(kv.Key, out var v) && v == kv.Value);
}
