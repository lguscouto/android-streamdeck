# Avisos de terceiros — dependências .NET do provider AMD

Este inventário acompanha o bundle Windows quando o provider AMD é empacotado. As versões são as resolvidas pelo projeto `server/native/gpu_telemetry_bridge/GpuTelemetryBridge.csproj` no build validado.

## Componentes e licenças

| Pacote | Versão | Licença / aviso | Origem |
|---|---:|---|---|
| LibreHardwareMonitorLib | 0.9.6 | MPL-2.0 | https://github.com/LibreHardwareMonitor/LibreHardwareMonitor |
| DiskInfoToolkit | 1.1.2 | MPL-2.0 | https://github.com/Blacktempel/DiskInfoToolkit |
| RAMSPDToolkit-NDD | 1.4.2 | MPL-2.0 | https://github.com/Blacktempel/RAMSPDToolkit |
| BlackSharp.Core | 1.0.7 | MPL-2.0 | https://github.com/Blacktempel/BlackSharp |
| HidSharp | 2.6.4 | Apache-2.0 | https://software.seekye.com/hidsharp |
| Mono.Posix.NETStandard | 1.0.0 | aviso/licença do pacote NuGet | https://www.nuget.org/packages/Mono.Posix.NETStandard/1.0.0 |
| System.Management | 10.0.2 | MIT | https://github.com/dotnet/dotnet |
| System.CodeDom | 10.0.2 | MIT | https://github.com/dotnet/dotnet |
| System.IO.Ports | 10.0.3 | MIT | https://github.com/dotnet/dotnet |
| System.Threading.AccessControl | 10.0.3 | MIT | https://github.com/dotnet/dotnet |
| runtime.native.System.IO.Ports | 10.0.3 | MIT | https://github.com/dotnet/dotnet |
| Microsoft.DotNet.ILCompiler | 8.0.30 | MIT | https://github.com/dotnet/runtime |
| Microsoft.NET.ILLink.Tasks | 8.0.30 | MIT | https://github.com/dotnet/runtime |

A cópia integral da MPL-2.0 usada pelos componentes MPL está em `LICENSES/MPL-2.0.txt`. O pacote HidSharp inclui seu aviso Apache-2.0 no próprio pacote NuGet; a origem e a licença estão identificadas acima. Os componentes .NET da Microsoft são redistribuídos conforme os avisos/licenças publicados pelo projeto .NET.

O projeto não modifica os componentes de terceiros listados acima. Os binários nativos de driver NVIDIA/AMD não são redistribuídos por este repositório.
