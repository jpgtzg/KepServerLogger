using System.Runtime.Versioning;
using Metrics;
using Services;
using Config;

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

            Console.WriteLine($"CPU Usage: {CpuMetrics.GetTotalCpuUsage():F2}%");

            var (total, free) = RamMetrics.GetMemoryInfo();
            Console.WriteLine($"RAM: {total - free} / {total} KB used");

            // Service metrics

            // foreach (var svc in ServiceController.GetServices())
            // {
            //     Console.WriteLine($"{svc.ServiceName} - {svc.Status}");

            //     using var searcher = new ManagementObjectSearcher(
            //         $"SELECT ProcessId FROM Win32_Service WHERE Name = '{svc.ServiceName}'");

            //     foreach (ManagementObject obj in searcher.Get())
            //     {
            //         uint pid = (uint)obj["ProcessId"];

            //         if (pid != 0)
            //         {
            //             Console.WriteLine($"  → PID: {pid}");

            //             try
            //             {
            //                 var process = Process.GetProcessById((int)pid);
            //                 Console.WriteLine($"  → Process Name: {process.ProcessName}");
            //             }
            //             catch { }
            //         }
            //     }
            // }

            // int[] ids = [5252, 3252, 5092, 8008];

            // foreach (var process in Process.GetProcesses())
            // {
            //     if (ids.Contains(process.Id))
            //     {
            //         Console.WriteLine($"Process: {process.ProcessName} - ID: {process.Id}");
            //     }
            // }

            // Console.WriteLine("================================");

            // foreach (var svc in ServiceController.GetServices())
            // {

            //     Console.WriteLine($"{svc.ServiceName} - {svc.Status} - {svc.MachineName} - {svc.ServiceType}");
            //     var processes = Process.GetProcessesByName(svc.ServiceName);

            //     if (processes.Length > 0)
            //     {
            //         Console.WriteLine($"Service: {svc.DisplayName} - Status: {svc.Status} -  Process ID: {string.Join(", ", processes.Select(p => p.Id))}");
            //     }

            //     processes = Process.GetProcessesByName(svc.DisplayName);

            //     if (processes.Length > 0)
            //     {
            //         Console.WriteLine($"Service: {svc.DisplayName} - Status: {svc.Status} -  Process ID: {string.Join(", ", processes.Select(p => p.Id))}");
            //     }
            // }

            foreach (var svcName in ConfigLoader.ServiceNames)
            {
                ServiceInfo serviceInfo = ServiceManager.GetServiceInfo(svcName);

                Console.WriteLine($"{string.Join(", ", serviceInfo.ProcessIds)} - {serviceInfo.Name} - {serviceInfo.Status} - {serviceInfo.MachineName} - {serviceInfo.ServiceType}");
            }

            // Network metrics  

            // NetworkInterface[] interfaces = NetworkMetrics.GetNetworkInterfaces();
            // foreach (var ni in interfaces)
            // {
            //     Console.WriteLine($"Interface: {ni.Name}");
            //     Console.WriteLine($"  Status: {ni.OperationalStatus}");
            //     Console.WriteLine($"  Type: {ni.NetworkInterfaceType}");

            //     var stats = ni.GetIPv4Statistics();
            //     Console.WriteLine($"  Bytes Sent: {stats.BytesSent}");
            //     Console.WriteLine($"  Bytes Received: {stats.BytesReceived}");
            //     Console.WriteLine();
            // }

            Thread.Sleep(ConfigLoader.ReadInterval);
        }
    }
}
