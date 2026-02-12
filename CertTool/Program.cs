
using System;
using System.IO;
using System.Threading.Tasks;
using Opc.Ua;
using Opc.Ua.Client;
using Opc.Ua.Configuration;

class Program
{
    static async Task Main(string[] args)
    {
        string endpointUrl = "opc.tcp://172.0.0.1:49320"; // Change if needed

        var application = new ApplicationInstance
        {
            ApplicationName = "MinimalOpcUaClient",
            ApplicationType = ApplicationType.Client
        };

        // Create configuration
        var config = new ApplicationConfiguration
        {
            ApplicationName = "MinimalOpcUaClient",
            ApplicationType = ApplicationType.Client,
            ApplicationUri = $"urn:{System.Net.Dns.GetHostName()}:MinimalOpcUaClient",

            SecurityConfiguration = new SecurityConfiguration
            {
                ApplicationCertificate = new CertificateIdentifier
                {
                    StoreType = "Directory",
                    StorePath = "pki/own",
                    SubjectName = "CN=MinimalOpcUaClient"
                },

                TrustedPeerCertificates = new CertificateTrustList
                {
                    StoreType = "Directory",
                    StorePath = "pki/trusted"
                },

                TrustedIssuerCertificates = new CertificateTrustList
                {
                    StoreType = "Directory",
                    StorePath = "pki/issuer"
                },

                RejectedCertificateStore = new CertificateTrustList
                {
                    StoreType = "Directory",
                    StorePath = "pki/rejected"
                },

                AutoAcceptUntrustedCertificates = true
            },

            TransportConfigurations = new TransportConfigurationCollection(),
            TransportQuotas = new TransportQuotas
            {
                OperationTimeout = 15000
            },

            ClientConfiguration = new ClientConfiguration
            {
                DefaultSessionTimeout = 60000
            }
        };

        await config.ValidateAsync(ApplicationType.Client);

        application.ApplicationConfiguration = config;

        // Ensure certificate exists
        if (config.SecurityConfiguration.ApplicationCertificate.Certificate == null)
        {
            await application.CheckApplicationInstanceCertificatesAsync(false, 2048);
        }

        Console.WriteLine("Selecting endpoint...");

        var selectedEndpoint = CoreClientUtils.SelectEndpoint(config, endpointUrl, useSecurity: true);

        Console.WriteLine($"Selected Endpoint: {selectedEndpoint.EndpointUrl}");
        Console.WriteLine($"Security Policy: {selectedEndpoint.SecurityPolicyUri}");
        Console.WriteLine($"Message Security Mode: {selectedEndpoint.SecurityMode}");

        var endpoint = new ConfiguredEndpoint(
            null,
            selectedEndpoint,
            EndpointConfiguration.Create(config));

        Console.WriteLine("Creating session...");

        using var session = await Session.Create(
            config,
            endpoint,
            false,
            "MinimalSession",
            60000,
            null,
            null);

        Console.WriteLine("Connected to server!");

        // READ NODE (Change NodeId if needed)
        var nodeToRead = new ReadValueId
        {
            NodeId = new NodeId("ns=2;s=Demo.Static.Scalar.Double"),
            AttributeId = Attributes.Value
        };

        var nodesToRead = new ReadValueIdCollection { nodeToRead };

        session.Read(
            null,
            0,
            TimestampsToReturn.Neither,
            nodesToRead,
            out DataValueCollection results,
            out DiagnosticInfoCollection _);

        if (StatusCode.IsGood(results[0].StatusCode))
        {
            Console.WriteLine($"Value: {results[0].Value}");
        }
        else
        {
            Console.WriteLine($"Read failed: {results[0].StatusCode}");
        }

        session.Close();
        Console.WriteLine("Disconnected.");
    }
}
