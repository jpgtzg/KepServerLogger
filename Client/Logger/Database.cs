using System;
using Microsoft.Data.Sqlite;
using Events;
using System.Net.NetworkInformation;
using Services;

namespace Logger
{
    public static class Database
    {
        private static string connectionString = "Data Source=logs.db";
        private static SqliteConnection? _connection;
        private static SqliteTransaction? _transaction;

        public static void Initialize()
        {
            _connection = new SqliteConnection(connectionString);
            _connection.Open();

            var command = _connection.CreateCommand();
            command.CommandText =
            @"
                CREATE TABLE IF NOT EXISTS Events (
                    Id INTEGER PRIMARY KEY AUTOINCREMENT,
                    Timestamp TEXT NOT NULL,
                    EventName TEXT NOT NULL,
                    Source TEXT NOT NULL,
                    Message TEXT NOT NULL
                );
            ";
            command.ExecuteNonQuery();


            command.CommandText =
            @"
                CREATE TABLE IF NOT EXISTS CpuUsage (
                    Id INTEGER PRIMARY KEY AUTOINCREMENT,
                    Timestamp TEXT NOT NULL,
                    Usage REAL NOT NULL
                );
            ";
            command.ExecuteNonQuery();


            command.CommandText =
            @"
                CREATE TABLE IF NOT EXISTS NetworkUsage (
                    Id INTEGER PRIMARY KEY AUTOINCREMENT,
                    Interface TEXT NOT NULL,
                    OperationalStatus TEXT NOT NULL,
                    NetworkInterfaceType TEXT NOT NULL,
                    Timestamp TEXT NOT NULL,
                    KbBytesSent REAL NOT NULL,
                    KbBytesReceived REAL NOT NULL
                );
            ";
            command.ExecuteNonQuery();


            command.CommandText =
            @"
                CREATE TABLE IF NOT EXISTS RamUsage (
                    Id INTEGER PRIMARY KEY AUTOINCREMENT,
                    Timestamp TEXT NOT NULL,
                    TotalKb INTEGER NOT NULL,
                    FreeKb INTEGER NOT NULL
                );
            ";
            command.ExecuteNonQuery();
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
            verifyConnection();
            var command = _connection!.CreateCommand();

            if (_transaction != null)
                command.Transaction = _transaction;

            command.CommandText =
            @"
                INSERT INTO Events (Timestamp, EventName, Source, Message)
                VALUES ($timestamp, $eventName, $source, $message);
            ";
            command.Parameters.AddWithValue("$timestamp", evt.Timestamp);
            command.Parameters.AddWithValue("$eventName", evt.Name);
            command.Parameters.AddWithValue("$source", evt.Source);
            command.Parameters.AddWithValue("$message", evt.Message);

            command.ExecuteNonQuery();
        }

        public static void InsertCPUUsage(float cpuUsage)
        {
            verifyConnection();
            var command = _connection!.CreateCommand();

            // Use the current transaction if it exists
            if (_transaction != null)
                command.Transaction = _transaction;

            command.CommandText =
            @"
                INSERT INTO CpuUsage (Timestamp, Usage)
                VALUES ($timestamp, $usage);
            ";
            command.Parameters.AddWithValue("$timestamp", DateTime.UtcNow.ToString("o"));
            command.Parameters.AddWithValue("$usage", cpuUsage);

            command.ExecuteNonQuery();
        }

        public static void InsertNetworkMetrics(NetworkInterface ni)
        {
            verifyConnection();
            var command = _connection!.CreateCommand();

            // Use the current transaction if it exists
            if (_transaction != null)
                command.Transaction = _transaction;

            command.CommandText =
            @"
                INSERT INTO NetworkUsage (Interface, OperationalStatus, NetworkInterfaceType, Timestamp, KbBytesSent, KbBytesReceived)
                VALUES ($interface, $operationalStatus, $networkInterfaceType, $timestamp, $KbBytesSent, $KbBytesReceived);
            ";
            command.Parameters.AddWithValue("$interface", ni.Name);
            command.Parameters.AddWithValue("$operationalStatus", ni.OperationalStatus.ToString());
            command.Parameters.AddWithValue("$networkInterfaceType", ni.NetworkInterfaceType.ToString());
            command.Parameters.AddWithValue("$timestamp", DateTime.UtcNow.ToString("o"));
            command.Parameters.AddWithValue("$KbBytesSent", ni.GetIPStatistics().BytesSent / 1024.0);
            command.Parameters.AddWithValue("$KbBytesReceived", ni.GetIPStatistics().BytesReceived / 1024.0);

            command.ExecuteNonQuery();
        }

        public static void InsertRAMUsage(ulong totalKb, ulong freeKb)
        {
            verifyConnection();
            var command = _connection!.CreateCommand();

            // Use the current transaction if it exists
            if (_transaction != null)
                command.Transaction = _transaction;

            command.CommandText =
            @"
                INSERT INTO RamUsage (Timestamp, TotalKb, FreeKb)
                VALUES ($timestamp, $totalKb, $freeKb);
            ";
            command.Parameters.AddWithValue("$timestamp", DateTime.UtcNow.ToString("o"));
            command.Parameters.AddWithValue("$totalKb", totalKb);
            command.Parameters.AddWithValue("$freeKb", freeKb);

            command.ExecuteNonQuery();
        }

        public static void InsertServiceInfo(ServiceInfo serviceInfo)
        {
            verifyConnection();
            var command = _connection!.CreateCommand();

            if (_transaction != null)
                command.Transaction = _transaction;

            command.CommandText =
            @"
                INSERT INTO Services (Name, Status, ServiceType, MachineName, ProcessIds, Timestamp)
                VALUES ($name, $status, $serviceType, $machineName, $processIds, $timestamp);
            ";
            command.Parameters.AddWithValue("$name", serviceInfo.Name);
            command.Parameters.AddWithValue("$status", serviceInfo.Status.ToString());
            command.Parameters.AddWithValue("$serviceType", serviceInfo.ServiceType.ToString());
            command.Parameters.AddWithValue("$machineName", serviceInfo.MachineName);
            command.Parameters.AddWithValue("$processIds", string.Join(",", serviceInfo.ProcessIds));
            command.Parameters.AddWithValue("$timestamp", DateTime.UtcNow.ToString("o"));
            command.ExecuteNonQuery();
        }

        public static void Close()
        {
            _connection?.Close();
            _connection = null;
        }

        private static void verifyConnection()
        {
            if (_connection == null)
            {
                throw new InvalidOperationException("Database not initialized. Call Initialize() first.");
            }
        }
    }
}