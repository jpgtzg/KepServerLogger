using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using System.Text;
using System.Threading.Tasks;
using System.Net.Http.Headers;
using System.Security.Cryptography;

namespace Events
{
    public static class EventMetrics
    {
        private static HttpClient httpClient = new HttpClient();

        public static async Task<Event[]> GetEvents()
        {
            string? username = Environment.GetEnvironmentVariable("KEPSERVER_USERNAME"); // your username
            string? password = Environment.GetEnvironmentVariable("KEPSERVER_PASSWORD"); // your password
            string? url = Environment.GetEnvironmentVariable("EVENT_LOG_URL");

            if (string.IsNullOrEmpty(username) || string.IsNullOrEmpty(password) || string.IsNullOrEmpty(url))
            {
                throw new InvalidOperationException("Environment variables KEPSERVER_USERNAME, KEPSERVER_PASSWORD, and EVENT_LOG_URL must be set.");   
            }

            // Encode username:password in Base64
            var byteArray = Encoding.ASCII.GetBytes($"{username}:{password}");
            httpClient.DefaultRequestHeaders.Authorization =
                new AuthenticationHeaderValue("Basic", Convert.ToBase64String(byteArray));

            // Make the GET request
            var response = await httpClient.GetAsync(url);
            response.EnsureSuccessStatusCode();

            // Read response content once and handle possible null deserialization result
            string json = await response.Content.ReadAsStringAsync();
            Event[] events = JsonSerializer.Deserialize<Event[]>(json) ?? Array.Empty<Event>();

            foreach (var ev in events)
            {
                string prehash = $"{ev.Name}|{ev.Source}|{ev.Message}|{ev.Timestamp}";

                byte[] hashBytes = SHA256.HashData(Encoding.UTF8.GetBytes(prehash));
                string hash = Convert.ToHexString(hashBytes);

                ev.Hash = hash;
            }

            return events;
        }
    }
}