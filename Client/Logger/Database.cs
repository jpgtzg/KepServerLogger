using System;
using Microsoft.Data.Sqlite;
using Events;
using System.Net.NetworkInformation;

namespace Logger
{
    public static class Database
    {
        private static string connectionString = "Data Source=logs.db";

        public static void Initialize()
        {
            using var connection = new SqliteConnection(connectionString);
            connection.Open();

            var command = connection.CreateCommand();
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
                    KbBytesSent INTEGER NOT NULL,
                    KbBytesReceived INTEGER NOT NULL
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

        public static void InsertEvent(Event evt)
        {
            using var connection = new SqliteConnection(connectionString);
            connection.Open();

            var command = connection.CreateCommand();
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
            using var connection = new SqliteConnection(connectionString);
            connection.Open();

            var command = connection.CreateCommand();
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
            using var connection = new SqliteConnection(connectionString);
            connection.Open();

            var command = connection.CreateCommand();
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
            using var connection = new SqliteConnection(connectionString);
            connection.Open();

            var command = connection.CreateCommand();
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
    }
}