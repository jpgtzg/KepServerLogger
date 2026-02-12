using System.Management;
using System.ServiceProcess;
using System.Diagnostics;
using System.Runtime.Versioning;

namespace Services
{
    public class ServiceInfo
    {
        public required string Name { get; set; }
        public ServiceControllerStatus Status { get; set; }

        public required ServiceType ServiceType { get; set; }
        public required string MachineName { get; set; }
        public required List<int> ProcessIds { get; set; }
    }

    public static class ServiceManager
    {
        [SupportedOSPlatform("windows")]
        public static ServiceInfo GetServiceInfo(string serviceName)
        {
            try
            {
                ServiceController svc = new ServiceController(serviceName);

                using var searcher = new ManagementObjectSearcher(
    $"SELECT ProcessId FROM Win32_Service WHERE Name = '{svc.ServiceName}'");

                List<int> processIds = new List<int>();

                foreach (ManagementObject obj in searcher.Get())
                {
                    uint pid = (uint)obj["ProcessId"];

                    if (pid != 0)
                    {
                        processIds.Add((int)pid);
                    }
                }

                return new ServiceInfo
                {
                    Name = svc.ServiceName,
                    Status = svc.Status,
                    ServiceType = svc.ServiceType,
                    MachineName = svc.MachineName,
                    ProcessIds = processIds
                };
            }
            catch (Exception ex)
            {
                throw new Exception($"Error retrieving service '{serviceName}': {ex.Message}");
            }
        }
    }
}