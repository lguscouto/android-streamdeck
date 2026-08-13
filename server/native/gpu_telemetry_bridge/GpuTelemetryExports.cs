using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

namespace StreamDeck.GpuTelemetryBridge;

[StructLayout(LayoutKind.Sequential)]
public struct AmdGpuTelemetryNative
{
    public uint AbiVersion;
    public int ProviderIndex;
    public int IsDiscrete;
    public int TemperatureCelsius;
    public ulong UsedBytes;
    public ulong TotalBytes;
}

public static class GpuTelemetryExports
{
    private const uint AbiVersion = 1;
    private const int NativeNaTemperature = int.MinValue;

    [UnmanagedCallersOnly(
        EntryPoint = "streamdeck_gpu_bridge_abi_version",
        CallConvs = new[] { typeof(CallConvCdecl) })]
    public static uint GetAbiVersion() => AbiVersion;

    [UnmanagedCallersOnly(
        EntryPoint = "streamdeck_read_amd_gpus",
        CallConvs = new[] { typeof(CallConvCdecl) })]
    public static unsafe uint ReadAmdGpus(AmdGpuTelemetryNative* buffer, uint capacity)
    {
        IReadOnlyList<AmdTelemetryReading> readings;
        try
        {
            readings = AmdTelemetryReader.Read();
        }
        catch
        {
            readings = Array.Empty<AmdTelemetryReading>();
        }

        var required = (uint)readings.Count;
        if (buffer is null || capacity == 0)
        {
            return required;
        }

        var count = Math.Min(required, capacity);
        for (var index = 0; index < count; index++)
        {
            var reading = readings[index];
            buffer[index] = new AmdGpuTelemetryNative
            {
                AbiVersion = AbiVersion,
                ProviderIndex = reading.ProviderIndex,
                IsDiscrete = reading.IsDiscrete,
                TemperatureCelsius = reading.TemperatureCelsius ?? NativeNaTemperature,
                UsedBytes = reading.UsedBytes ?? 0,
                TotalBytes = reading.TotalBytes ?? 0,
            };
        }

        return count;
    }
}
