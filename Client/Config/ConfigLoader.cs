namespace Config
{

    public enum MetricType
    {
        Cpu,
        Ram,
        Network,
        Services
    }
    public static class ConfigLoader
    {
        public static int ReadInterval { get; private set; } = 1000;

        public static string[] ServiceNames { get; private set; } = new string[0];

        public static MetricType[] LoggingMetrics { get; private set; } = new MetricType[0];

        public static void LoadConfig()
        {
            var json = File.ReadAllText("settings.json");
            var config = System.Text.Json.JsonDocument.Parse(json).RootElement;

            if (config.TryGetProperty("read_interval", out var intervalProp))
            {
                ReadInterval = intervalProp.GetInt32();
            }

            if (config.TryGetProperty("services", out var servicesProp) && servicesProp.ValueKind == System.Text.Json.JsonValueKind.Array)
            {
                var services = new List<string>();
                foreach (var svc in servicesProp.EnumerateArray())
                {
                    services.Add(svc.GetString() ?? string.Empty);
                }
                ServiceNames = services.ToArray();
            }

            if (config.TryGetProperty("logging", out var loggingProp) && loggingProp.ValueKind == System.Text.Json.JsonValueKind.Array)
            {
                var metrics = new List<string>();
                foreach (var metric in loggingProp.EnumerateArray())
                {
                    metrics.Add(metric.GetString() ?? string.Empty);
                }
                LoggingMetrics = metrics.Select(m => m.ToLower() switch
                {
                    "cpu" => MetricType.Cpu,
                    "ram" => MetricType.Ram,
                    "network" => MetricType.Network,
                    "services" => MetricType.Services,
                    _ => throw new Exception($"Unknown metric type: {m}")
                }).ToArray();
            }
        }
    }
}