using System.Net.NetworkInformation;

namespace Metrics
{
    public static class NetworkMetrics
    {
        public static NetworkInterface[] GetNetworkInterfaces()
        {
            return NetworkInterface.GetAllNetworkInterfaces();
        }

        public static IPv4InterfaceStatistics[] GetNetworkStats()
        {
            return NetworkInterface.GetAllNetworkInterfaces()
                    .Select(ni => ni.GetIPv4Statistics())
                    .ToArray();

        }
    }
}
