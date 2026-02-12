// using Opc.Ua;
// using Opc.Ua.Configuration;
// using System;
// using System.IO;
// using System.Threading.Tasks;

// namespace KepServerLogger.Connection
// {
//     public class CertHelper
//     {
//         public const string CertPath = "certs/client_cert.pfx";
//         public const string CertPassword = "password"; // Protect your PFX

//         // public static async Task<ApplicationConfiguration> CreateClientConfig(string appName, string appUri)
//         // {
//         //     Directory.CreateDirectory("certs");

//         //     var config = new ApplicationConfiguration()
//         //     {
//         //         ApplicationName = appName,
//         //         ApplicationUri = appUri,
//         //         ApplicationType = ApplicationType.Client,
//         //         SecurityConfiguration = new SecurityConfiguration
//         //         {
//         //             ApplicationCertificate = new CertificateIdentifier
//         //             {
//         //                 StoreType = "Directory",
//         //                 StorePath = "certs",
//         //                 SubjectName = appUri
//         //             },
//         //             TrustedPeerCertificates = new CertificateTrustList
//         //             {
//         //                 StoreType = "Directory",
//         //                 StorePath = "certs/trusted"
//         //             },
//         //             AutoAcceptUntrustedCertificates = false
//         //         },
//         //         TransportConfigurations = new TransportConfigurationCollection(),
//         //         TransportQuotas = new TransportQuotas { OperationTimeout = 15000 },
//         //         ClientConfiguration = new ClientConfiguration { DefaultSessionTimeout = 60000 }
//         //     };

//         //     await config.Validate(ApplicationType.Client); 

//         //     // Check if a certificate exists
//         //     var certFile = Path.Combine("certs", "client_cert.pfx");
//         //     if (!File.Exists(certFile))
//         //     {
//         //         Console.WriteLine("Generating new client certificate...");
//         //         var certificate = CertificateFactory.CreateCertificate(
//         //             "CN=" + appName,
//         //             2048,
//         //             DateTime.UtcNow - TimeSpan.FromDays(1),
//         //             DateTime.UtcNow + TimeSpan.FromDays(365),
//         //             null,
//         //             null,
//         //             null
//         //         );

//         //         certificate.SaveAsPfx(certFile, CertPassword);
//         //         Console.WriteLine("Certificate generated at " + certFile);
//         //     }
//         //     else
//         //     {
//         //         Console.WriteLine("Certificate already exists at " + certFile);
//         //     }

//         //     return config;
//         // }
//     }
// }