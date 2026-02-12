using System.Runtime.Versioning;
using Metrics;
using Services;
using Config;
using System.Net.NetworkInformation;
class Program
{
    [SupportedOSPlatform("windows")]

    static void Main()
    {
        ConfigLoader.LoadConfig();

        while (true)
        {
            Console.Clear();

            // Computer Metrics

            if (ConfigLoader.LoggingMetrics.Contains(MetricType.Cpu))
            {
                Console.WriteLine($"CPU Usage: {CpuMetrics.GetTotalCpuUsage():F2}%");
            }

            if (ConfigLoader.LoggingMetrics.Contains(MetricType.Ram))
            {
                var (total, free) = RamMetrics.GetMemoryInfo();
                Console.WriteLine($"RAM: {total - free} / {total} KB used");
            }

            // Service metrics

            if (ConfigLoader.LoggingMetrics.Contains(MetricType.Services))
            {
                foreach (var svcName in ConfigLoader.ServiceNames)
                {
                    ServiceInfo serviceInfo = ServiceManager.GetServiceInfo(svcName);

                    Console.WriteLine($"{string.Join(", ", serviceInfo.ProcessIds)} - {serviceInfo.Name} - {serviceInfo.Status} - {serviceInfo.MachineName} - {serviceInfo.ServiceType}");
                }
            }

            // Network metrics  

            if (ConfigLoader.LoggingMetrics.Contains(MetricType.Network))
            {
                NetworkInterface[] interfaces = NetworkMetrics.GetNetworkInterfaces();
                foreach (var ni in interfaces)
                {
                    Console.WriteLine($"Interface: {ni.Name}");
                    Console.WriteLine($"  Status: {ni.OperationalStatus}");
                    Console.WriteLine($"  Type: {ni.NetworkInterfaceType}");

                    var stats = ni.GetIPv4Statistics();
                    Console.WriteLine($"  Bytes Sent: {stats.BytesSent}");
                    Console.WriteLine($"  Bytes Received: {stats.BytesReceived}");
                    Console.WriteLine();
                }
            }

            Thread.Sleep(ConfigLoader.ReadInterval);
        }
    }
}
