using Npgsql;
using Events;
using System.Net.NetworkInformation;
using Services;

namespace Logger
{
    public static class Database
    {
        private static string? _connectionString;
        private static NpgsqlConnection? _connection;
        private static NpgsqlTransaction? _transaction;
        private static int retentionDays = 7;

        public static void Initialize()
        {
            string? db_host = Environment.GetEnvironmentVariable("DB_HOST") ?? "localhost";
            string? db_port = Environment.GetEnvironmentVariable("DB_PORT") ?? "5432";
            string? db_name = Environment.GetEnvironmentVariable("DB_NAME");
            string? db_user = Environment.GetEnvironmentVariable("DB_USER");
            string? db_password = Environment.GetEnvironmentVariable("DB_PASSWORD");

            if (string.IsNullOrEmpty(db_name) || string.IsNullOrEmpty(db_user) || string.IsNullOrEmpty(db_password))
                throw new InvalidOperationException("DB_NAME, DB_USER, and DB_PASSWORD must be set.");

            string _retentionDaysStr = Environment.GetEnvironmentVariable("LOG_RETENTION_DAYS") ?? "7";
            if (!int.TryParse(_retentionDaysStr, out retentionDays))
            {
                Console.WriteLine($"Invalid LOG_RETENTION_DAYS value '{_retentionDaysStr}', defaulting to 7.");
                retentionDays = 7;
            }

            _connectionString = $"Host={db_host};Port={db_port};Database={db_name};Username={db_user};Password={db_password}";
            _connection = new NpgsqlConnection(_connectionString);
            _connection.Open();

            // Schema creation
            using var cmd = _connection.CreateCommand();
            cmd.CommandText = @"
                CREATE TABLE IF NOT EXISTS events (
                    hash        TEXT PRIMARY KEY NOT NULL,
                    timestamp   TIMESTAMPTZ NOT NULL,
                    event_name  TEXT NOT NULL,
                    source      TEXT NOT NULL,
                    message     TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cpu_usage (
                    timestamp   TIMESTAMPTZ NOT NULL,
                    usage       REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS network_usage (
                    timestamp               TIMESTAMPTZ NOT NULL,
                    interface               TEXT NOT NULL,
                    operational_status      TEXT NOT NULL,
                    network_interface_type  TEXT NOT NULL,
                    kb_bytes_sent           REAL NOT NULL,
                    kb_bytes_received       REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ram_usage (
                    timestamp   TIMESTAMPTZ NOT NULL,
                    total_kb    BIGINT NOT NULL,
                    free_kb     BIGINT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS services (
                    timestamp       TIMESTAMPTZ NOT NULL,
                    name            TEXT NOT NULL,
                    status          TEXT NOT NULL,
                    service_type    TEXT NOT NULL,
                    machine_name    TEXT NOT NULL,
                    process_ids     TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_cpu_timestamp       ON cpu_usage (timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_network_timestamp   ON network_usage (timestamp DESC, interface);
                CREATE INDEX IF NOT EXISTS idx_ram_timestamp       ON ram_usage (timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_services_timestamp  ON services (timestamp DESC, name);
                CREATE INDEX IF NOT EXISTS idx_events_timestamp    ON events (timestamp DESC);
            ";
            cmd.ExecuteNonQuery();

            // Convert to hypertables (safe to call repeatedly — IF NOT EXISTS)
            ConvertToHypertable("cpu_usage");
            ConvertToHypertable("network_usage");
            ConvertToHypertable("ram_usage");
            ConvertToHypertable("services");
        }

        private static void ConvertToHypertable(string table)
        {
            using var cmd = _connection!.CreateCommand();
            cmd.CommandText = $"SELECT create_hypertable('{table}', 'timestamp', if_not_exists => TRUE);";
            cmd.ExecuteNonQuery();
        }

        public static void OpenTransaction()
        {
            verifyConnection();
            if (_transaction != null)
                throw new InvalidOperationException("Transaction already open.");
            _transaction = _connection!.BeginTransaction();
        }

        public static void CloseTransaction()
        {
            if (_transaction == null)
                throw new InvalidOperationException("No transaction is open.");
            _transaction.Commit();
            _transaction.Dispose();
            _transaction = null;
        }

        public static void RollbackTransaction()
        {
            if (_transaction != null)
            {
                _transaction.Rollback();
                _transaction.Dispose();
                _transaction = null;
            }
        }

        public static void InsertEvent(Event evt)
        {
            if (evt.Hash == null)
                throw new ArgumentException("Event hash cannot be null.");

            verifyConnection();
            using var cmd = _connection!.CreateCommand();
            if (_transaction != null) cmd.Transaction = _transaction;

            cmd.CommandText = @"
                INSERT INTO events (hash, timestamp, event_name, source, message)
                VALUES (@hash, @timestamp, @event_name, @source, @message)
                ON CONFLICT (hash) DO NOTHING;
            ";

            cmd.Parameters.AddWithValue("hash", evt.Hash);
            // Explicitly specify UTC kind to ensure Postgres treats it as TIMESTAMPTZ
            cmd.Parameters.AddWithValue("timestamp", DateTime.SpecifyKind(DateTime.UtcNow, DateTimeKind.Utc));
            cmd.Parameters.AddWithValue("event_name", evt.Name);
            cmd.Parameters.AddWithValue("source", evt.Source);
            cmd.Parameters.AddWithValue("message", evt.Message);

            cmd.ExecuteNonQuery();
        }

        public static void InsertCPUUsage(float cpuUsage)
        {
            verifyConnection();
            using var cmd = _connection!.CreateCommand();
            if (_transaction != null) cmd.Transaction = _transaction;
            cmd.CommandText = "INSERT INTO cpu_usage (timestamp, usage) VALUES (@timestamp, @usage);";
            cmd.Parameters.AddWithValue("timestamp", DateTime.SpecifyKind(DateTime.UtcNow, DateTimeKind.Utc));
            cmd.Parameters.AddWithValue("usage", cpuUsage);
            cmd.ExecuteNonQuery();
        }

        public static void InsertNetworkMetrics(NetworkInterface ni)
        {
            verifyConnection();
            using var cmd = _connection!.CreateCommand();
            if (_transaction != null) cmd.Transaction = _transaction;
            cmd.CommandText = @"
                INSERT INTO network_usage (timestamp, interface, operational_status, network_interface_type, kb_bytes_sent, kb_bytes_received)
                VALUES (@timestamp, @interface, @op_status, @ni_type, @sent, @received);
            ";
            cmd.Parameters.AddWithValue("timestamp", DateTime.SpecifyKind(DateTime.UtcNow, DateTimeKind.Utc));
            cmd.Parameters.AddWithValue("interface", ni.Name);
            cmd.Parameters.AddWithValue("op_status", ni.OperationalStatus.ToString());
            cmd.Parameters.AddWithValue("ni_type", ni.NetworkInterfaceType.ToString());
            cmd.Parameters.AddWithValue("sent", ni.GetIPStatistics().BytesSent / 1024.0);
            cmd.Parameters.AddWithValue("received", ni.GetIPStatistics().BytesReceived / 1024.0);
            cmd.ExecuteNonQuery();
        }

        public static void InsertRAMUsage(ulong totalKb, ulong freeKb)
        {
            verifyConnection();
            using var cmd = _connection!.CreateCommand();
            if (_transaction != null) cmd.Transaction = _transaction;
            cmd.CommandText = "INSERT INTO ram_usage (timestamp, total_kb, free_kb) VALUES (@timestamp, @total, @free);";
            cmd.Parameters.AddWithValue("timestamp", DateTime.SpecifyKind(DateTime.UtcNow, DateTimeKind.Utc));
            cmd.Parameters.AddWithValue("total", (long)totalKb);
            cmd.Parameters.AddWithValue("free", (long)freeKb);
            cmd.ExecuteNonQuery();
        }

        public static void InsertServiceInfo(ServiceInfo serviceInfo)
        {
            verifyConnection();
            using var cmd = _connection!.CreateCommand();
            if (_transaction != null) cmd.Transaction = _transaction;
            cmd.CommandText = @"
                INSERT INTO services (timestamp, name, status, service_type, machine_name, process_ids)
                VALUES (@timestamp, @name, @status, @service_type, @machine_name, @process_ids);
            ";
            cmd.Parameters.AddWithValue("timestamp", DateTime.SpecifyKind(DateTime.UtcNow, DateTimeKind.Utc));
            cmd.Parameters.AddWithValue("name", serviceInfo.Name);
            cmd.Parameters.AddWithValue("status", serviceInfo.Status.ToString());
            cmd.Parameters.AddWithValue("service_type", serviceInfo.ServiceType.ToString());
            cmd.Parameters.AddWithValue("machine_name", serviceInfo.MachineName);
            cmd.Parameters.AddWithValue("process_ids", string.Join(",", serviceInfo.ProcessIds));
            cmd.ExecuteNonQuery();
        }

        // CleanupOldData is now a no-op — handled by TimescaleDB retention policy
        public static void CleanupOldData()
        {
            Console.WriteLine("Maintenance: Data retention is handled automatically by TimescaleDB.");
        }

        public static void Close()
        {
            _connection?.Close();
            _connection = null;
        }

        private static void verifyConnection()
        {
            if (_connection == null)
                throw new InvalidOperationException("Database not initialized. Call Initialize() first.");
        }
    }
}