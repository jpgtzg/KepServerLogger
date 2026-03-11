using System.Diagnostics;
using System.Runtime.Versioning;

namespace Metrics
{
    [SupportedOSPlatform("windows")]
    public static class CpuMetrics
    {
        private static PerformanceCounter cpuCounter = new PerformanceCounter("Processor", "% Processor Time", "_Total");
 
        public static float GetTotalCpuUsage()
        {
            cpuCounter.NextValue();
            Thread.Sleep(1000);
            return cpuCounter.NextValue();
        }
    }
}