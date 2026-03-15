using System.Runtime.Versioning;
using Metrics;
using Services;
using Config;
using System.Net.NetworkInformation;
using Events;
using Logger;
using DotNetEnv;

internal static class Program
{
    [SupportedOSPlatform("windows")]
    static void Main()
    {
        ConfigLoader.LoadConfig();
        Database.Initialize();
        Console.WriteLine("Database initialized successfully.");
        Env.Load();

        while (true)
        {
            int loggedSystemCount = 0;
            Database.OpenTransaction();
            try
            {
                // Computer Metrics

                if (ConfigLoader.LoggingMetrics.Contains(MetricType.Cpu))
                {
                    Database.InsertCPUUsage(CpuMetrics.GetTotalCpuUsage());
                    loggedSystemCount++;
                }

                if (ConfigLoader.LoggingMetrics.Contains(MetricType.Ram))
                {
                    var (total, free) = RamMetrics.GetMemoryInfo();
                    Database.InsertRAMUsage(total, free);
                    loggedSystemCount++;
                }

                // Service metrics

                if (ConfigLoader.LoggingMetrics.Contains(MetricType.Services))
                {
                    foreach (var svcName in ConfigLoader.ServiceNames)
                    {
                        ServiceInfo serviceInfo = ServiceManager.GetServiceInfo(svcName);
                        Database.InsertServiceInfo(serviceInfo);
                    }
                    loggedSystemCount++;
                }

                // Network metrics  

                if (ConfigLoader.LoggingMetrics.Contains(MetricType.Network))
                {
                    NetworkInterface[] interfaces = NetworkMetrics.GetNetworkInterfaces();
                    foreach (var ni in interfaces)
                    {
                        Database.InsertNetworkMetrics(ni);
                    }
                    loggedSystemCount++;
                }

                // KepServer Event Log
                if (ConfigLoader.LoggingMetrics.Contains(MetricType.KepServerEvents))
                {
                    Event[] events = EventMetrics.GetEvents().GetAwaiter().GetResult();
                    foreach (var ev in events)
                    {
                        Database.InsertEvent(ev);
                    }
                    loggedSystemCount++;
                }

                Database.CloseTransaction();
                Console.WriteLine($"Logged metrics for {loggedSystemCount} categories at {DateTime.Now}");
            }
            catch (Exception ex)
            {
                Console.WriteLine("Error occurred during metrics collection. Rolling back transaction." + ex.Message);
                Database.RollbackTransaction();
                throw;
            }

            Thread.Sleep(ConfigLoader.ReadInterval);
            Database.CleanupOldEvents();
        }
    }
}
