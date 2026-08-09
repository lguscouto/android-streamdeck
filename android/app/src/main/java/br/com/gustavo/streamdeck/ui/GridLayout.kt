package br.com.gustavo.streamdeck.ui

import br.com.gustavo.streamdeck.network.StreamDeckButton
import br.com.gustavo.streamdeck.network.StreamDeckPage

data class GridCell(
    val row: Int,
    val column: Int,
    val button: StreamDeckButton?,
)

object GridLayout {
    fun cells(page: StreamDeckPage): List<GridCell> {
        val buttonsByPosition = page.buttons.associateBy { button ->
            button.row to button.column
        }
        return buildList(page.rows * page.columns) {
            for (row in 0 until page.rows) {
                for (column in 0 until page.columns) {
                    add(
                        GridCell(
                            row = row,
                            column = column,
                            button = buttonsByPosition[row to column],
                        ),
                    )
                }
            }
        }
    }
}
