package com.upatriagem.app.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class ApiException(mensagem: String) : IOException(mensagem)

/** Cliente HTTP do backend (FastAPI) que roda no notebook ou no servidor da prefeitura. */
class Api(baseUrl: String) {
    private val base = baseUrl.trimEnd('/')

    val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
    }

    private suspend fun requisicao(caminho: String, metodo: String = "GET", corpo: String? = null): String =
        withContext(Dispatchers.IO) {
            val conn = URL(base + caminho).openConnection() as HttpURLConnection
            try {
                conn.requestMethod = metodo
                conn.connectTimeout = 5_000
                // A primeira chamada de previsões treina os modelos e pode levar alguns segundos.
                conn.readTimeout = 60_000
                conn.setRequestProperty("Accept", "application/json")
                if (corpo != null) {
                    conn.doOutput = true
                    conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    conn.outputStream.use { it.write(corpo.toByteArray(Charsets.UTF_8)) }
                }
                val codigo = conn.responseCode
                val stream = if (codigo in 200..299) conn.inputStream else conn.errorStream
                val texto = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() }.orEmpty()
                if (codigo !in 200..299) throw ApiException("Erro $codigo do servidor: ${texto.take(200)}")
                texto
            } finally {
                conn.disconnect()
            }
        }

    private fun q(v: String) = URLEncoder.encode(v, "UTF-8")

    suspend fun config(): ConfigApp = json.decodeFromString(requisicao("/api/config"))

    suspend fun triagem(entrada: TriagemEntrada): TriagemResultado =
        json.decodeFromString(requisicao("/api/triagem", "POST", json.encodeToString(entrada)))

    suspend fun unidades(lat: Double?, lon: Double?, tipos: Set<String>): UnidadesResposta {
        val params = buildList {
            if (lat != null && lon != null) {
                add("lat=$lat"); add("lon=$lon")
            }
            tipos.forEach { add("tipo=${q(it)}") }
        }
        val qs = if (params.isEmpty()) "" else "?" + params.joinToString("&")
        return json.decodeFromString(requisicao("/api/unidades$qs"))
    }

    suspend fun previsoes(semanas: Int = 8): ResumoPrevisoes =
        json.decodeFromString(requisicao("/api/previsoes?semanas=$semanas"))

    suspend fun dadosUteis(): DadosUteis = json.decodeFromString(requisicao("/api/dados-uteis"))
}
