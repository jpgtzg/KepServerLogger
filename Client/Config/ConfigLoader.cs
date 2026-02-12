namespace Config
{
    public static class ConfigLoader
    {
        public static int ReadInterval { get; private set; } = 1000;

        public static string[] ServiceNames { get; private set; } = new string[0];

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
        }
    }
}