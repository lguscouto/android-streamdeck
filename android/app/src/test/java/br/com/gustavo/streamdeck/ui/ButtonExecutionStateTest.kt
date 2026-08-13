package br.com.gustavo.streamdeck.ui

import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckKeyAction
import br.com.gustavo.streamdeck.network.StreamDeckSystemInfoAction
import org.junit.Assert.assertEquals
import org.junit.Test

class ButtonExecutionStateTest {
    @Test
    fun `telemetria exibe a mensagem de resultado do servidor`() {
        assertEquals(
            "CPU: 42% | N/A",
            completedActionMessage(
                button = button(StreamDeckSystemInfoAction("cpu")),
                acknowledgementMessage = "CPU: 42% | N/A",
                defaultMessage = "Concluído",
            ),
        )
    }

    @Test
    fun `ações comuns preservam o feedback localizado`() {
        assertEquals(
            "Concluído",
            completedActionMessage(
                button = button(StreamDeckKeyAction("PRINTSCREEN")),
                acknowledgementMessage = "Action completed",
                defaultMessage = "Concluído",
            ),
        )
    }

    @Test
    fun `telemetria sem mensagem usa o feedback localizado`() {
        assertEquals(
            "Concluído",
            completedActionMessage(
                button = button(StreamDeckSystemInfoAction("memory")),
                acknowledgementMessage = null,
                defaultMessage = "Concluído",
            ),
        )
    }

    @Test
    fun `telemetria rejeita mensagem fora do formato público esperado`() {
        assertEquals(
            "Concluído",
            completedActionMessage(
                button = button(StreamDeckSystemInfoAction("cpu")),
                acknowledgementMessage = "token=caminho-interno",
                defaultMessage = "Concluído",
            ),
        )
    }

    @Test
    fun `telemetria rejeita formato de outro alvo`() {
        assertEquals(
            "Concluído",
            completedActionMessage(
                button = button(StreamDeckSystemInfoAction("memory")),
                acknowledgementMessage = "CPU: 42% | N/A",
                defaultMessage = "Concluído",
            ),
        )
    }

    @Test
    fun `telemetria gpu exibe temperatura e vram do servidor`() {
        assertEquals(
            "GPU: 61°C | VRAM: 2.0/8.0 GB (25%)",
            completedActionMessage(
                button = button(StreamDeckSystemInfoAction("gpu")),
                acknowledgementMessage = "GPU: 61°C | VRAM: 2.0/8.0 GB (25%)",
                defaultMessage = "Concluído",
            ),
        )
    }

    private fun button(action: br.com.gustavo.streamdeck.network.StreamDeckAction) = StreamDeckButton(
        id = "test-button",
        row = 0,
        column = 0,
        title = "Teste",
        icon = null,
        color = null,
        action = action,
    )
}