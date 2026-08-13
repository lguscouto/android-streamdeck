# Licenças e avisos de terceiros

## LibreHardwareMonitorLib 0.9.6

O provider AMD opcional usa `LibreHardwareMonitorLib` versão `0.9.6`, distribuída sob a licença **Mozilla Public License 2.0 (MPL-2.0)**.

- Projeto upstream: https://github.com/LibreHardwareMonitor/LibreHardwareMonitor
- Pacote NuGet: https://www.nuget.org/packages/LibreHardwareMonitorLib/0.9.6
- O binário é consumido como dependência de build; não é um driver proprietário nem substitui o driver AMD instalado pelo usuário.
- O bundle inclui este aviso, o inventário transitivo e os textos de licença em `LICENSES/`.

## Dependências transitivas do provider AMD

As dependências .NET transitivas e suas versões/licenças estão listadas em `LICENSES/THIRD-PARTY-DOTNET.md`. O bundle também inclui os textos Apache-2.0 e MIT usados pelos componentes correspondentes. A MPL-2.0 integral está em `LICENSES/MPL-2.0.txt`.

## Componentes fornecidos pelo driver

O projeto não redistribui ADLX, `amd-smi`, `nvidia-smi`, DLLs proprietárias de driver ou SDKs proprietários. O provider NVIDIA depende do NVML/driver NVIDIA já instalado no sistema e o provider AMD depende da disponibilidade do LibreHardwareMonitor e do driver AMD compatível. Sem esses componentes, o servidor permanece funcional e retorna `GPU: N/A | VRAM: N/A`.
