using System.Management;
using System.Runtime.Versioning;

namespace Metrics
{
    [SupportedOSPlatform("windows")]
    public static class RamMetrics
    {
        public static (ulong Total, ulong Free) GetMemoryInfo()
        {
            var searcher = new ManagementObjectSearcher("SELECT TotalVisibleMemorySize, FreePhysicalMemory FROM Win32_OperatingSystem");
            foreach (var obj in searcher.Get())
            {
                ulong total = (ulong)obj["TotalVisibleMemorySize"];
                ulong free = (ulong)obj["FreePhysicalMemory"];
                return (total, free);
            }
            return (0, 0);
        }
    }
}