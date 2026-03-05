using System.Text.Json.Serialization;

namespace Events
{

    public class Event
    {
        [JsonPropertyName("timestamp")]
        public string Timestamp { get; }
        [JsonPropertyName("event")]
        public string Name { get; }
        [JsonPropertyName("source")]
        public string Source { get;  }

        [JsonPropertyName("message")]
        public string Message { get; }

        public string? Hash { get; set; }        
    
        public Event(string timestamp, string name, string source, string message)
        {
            Timestamp = timestamp;
            Name = name;
            Source = source;
            Message = message;
        }
    }
}