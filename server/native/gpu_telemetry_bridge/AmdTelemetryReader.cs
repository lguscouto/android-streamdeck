using LibreHardwareMonitor.Hardware;

namespace StreamDeck.GpuTelemetryBridge;

internal readonly record struct AmdTelemetryReading(
    int ProviderIndex,
    int IsDiscrete,
    int? TemperatureCelsius,
    ulong? UsedBytes,
    ulong? TotalBytes);

internal static class AmdTelemetryReader
{
    private const string GpuCoreTemperature = "GPU Core";
    private const string DedicatedUsed = "D3D Dedicated Memory Used";
    private const string DedicatedTotal = "D3D Dedicated Memory Total";
    private const string GenericUsed = "GPU Memory Used";
    private const string GenericTotal = "GPU Memory Total";
    private const double BytesPerMebibyte = 1024d * 1024d;

    internal static IReadOnlyList<AmdTelemetryReading> Read()
    {
        var computer = new Computer
        {
            IsGpuEnabled = true,
            IsCpuEnabled = false,
            IsMemoryEnabled = false,
            IsMotherboardEnabled = false,
            IsStorageEnabled = false,
            IsControllerEnabled = false,
            IsNetworkEnabled = false,
            IsBatteryEnabled = false,
            IsPowerMonitorEnabled = false,
            IsPsuEnabled = false,
        };

        try
        {
            computer.Open();
            var result = new List<AmdTelemetryReading>();
            var providerIndex = 0;
            foreach (var hardware in computer.Hardware)
            {
                if (hardware.HardwareType != HardwareType.GpuAmd)
                {
                    continue;
                }

                try
                {
                    hardware.Update();
                    result.Add(ReadHardware(hardware, providerIndex));
                }
                catch
                {
                    // A broken or inaccessible GPU must not prevent other
                    // providers from returning data or leak internals over ABI.
                    result.Add(new AmdTelemetryReading(providerIndex, -1, null, null, null));
                }

                providerIndex++;
            }

            return result;
        }
        catch
        {
            return Array.Empty<AmdTelemetryReading>();
        }
        finally
        {
            try
            {
                computer.Close();
            }
            catch
            {
                // Cleanup is best effort at the native boundary.
            }
        }
    }

    private static AmdTelemetryReading ReadHardware(IHardware hardware, int providerIndex)
    {
        var sensors = hardware.Sensors;
        var temperature = ReadTemperature(sensors);
        var dedicatedUsed = ReadSmallData(sensors, DedicatedUsed);
        var dedicatedTotal = ReadSmallData(sensors, DedicatedTotal);
        var genericUsed = ReadSmallData(sensors, GenericUsed);
        var genericTotal = ReadSmallData(sensors, GenericTotal);

        var memory = NormalizeMemory(dedicatedUsed, dedicatedTotal)
            ?? NormalizeMemory(genericUsed, genericTotal);

        return new AmdTelemetryReading(
            providerIndex,
            IsDiscrete: 1,
            temperature,
            memory?.UsedBytes,
            memory?.TotalBytes);
    }

    private static int? ReadTemperature(IEnumerable<ISensor> sensors)
    {
        foreach (var sensor in sensors)
        {
            if (sensor.SensorType != SensorType.Temperature ||
                !string.Equals(sensor.Name, GpuCoreTemperature, StringComparison.Ordinal))
            {
                continue;
            }

            var value = sensor.Value;
            if (!value.HasValue || float.IsNaN(value.Value) || float.IsInfinity(value.Value))
            {
                return null;
            }

            var rounded = (int)Math.Round(value.Value, MidpointRounding.AwayFromZero);
            return rounded is >= 0 and <= 150 ? rounded : null;
        }

        return null;
    }

    private static double? ReadSmallData(IEnumerable<ISensor> sensors, string name)
    {
        foreach (var sensor in sensors)
        {
            if (sensor.SensorType != SensorType.SmallData ||
                !string.Equals(sensor.Name, name, StringComparison.Ordinal))
            {
                continue;
            }

            var value = sensor.Value;
            if (!value.HasValue || float.IsNaN(value.Value) || float.IsInfinity(value.Value))
            {
                return null;
            }

            return value.Value;
        }

        return null;
    }

    private static (ulong UsedBytes, ulong TotalBytes)? NormalizeMemory(
        double? usedMebibytes,
        double? totalMebibytes)
    {
        if (!usedMebibytes.HasValue || !totalMebibytes.HasValue ||
            usedMebibytes.Value < 0 || totalMebibytes.Value <= 0 ||
            usedMebibytes.Value > totalMebibytes.Value)
        {
            return null;
        }

        var used = usedMebibytes.Value * BytesPerMebibyte;
        var total = totalMebibytes.Value * BytesPerMebibyte;
        if (used > ulong.MaxValue || total > ulong.MaxValue)
        {
            return null;
        }

        return ((ulong)used, (ulong)total);
    }
}
