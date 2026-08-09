package br.com.gustavo.streamdeck

import org.junit.Assert.assertEquals
import org.junit.Test

class AppMetadataTest {
    @Test
    fun `identifica o produto e sua versao inicial`() {
        assertEquals("Android Stream Deck", AppMetadata.PRODUCT_NAME)
        assertEquals("0.1.0", AppMetadata.VERSION_NAME)
        assertEquals(1, AppMetadata.VERSION_CODE)
        assertEquals("br.com.gustavo.streamdeck", AppMetadata.APPLICATION_ID)
    }
}
