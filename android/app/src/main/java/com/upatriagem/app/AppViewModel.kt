package com.upatriagem.app

import android.app.Application
import android.content.Context
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.upatriagem.app.data.Api
import com.upatriagem.app.data.ConfigApp
import com.upatriagem.app.data.DadosUteis
import com.upatriagem.app.data.Ponto
import com.upatriagem.app.data.ResumoPrevisoes
import com.upatriagem.app.data.TriagemEntrada
import com.upatriagem.app.data.TriagemResultado
import com.upatriagem.app.data.UnidadesResposta
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Sintomas que, mesmo sem conexão com o servidor, indicam procurar emergência. */
val SINTOMAS_ALARME_OFFLINE = setOf("dor_peito", "falta_ar", "desmaio", "confusao", "convulsao", "fraqueza_lado", "sangramento")

class AppViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("upa_triagem", Context.MODE_PRIVATE)

    var apiUrl by mutableStateOf(prefs.getString("api_url", BuildConfig.API_URL_PADRAO)!!)
        private set
    private var api = Api(apiUrl)

    var config by mutableStateOf<ConfigApp?>(null)
        private set
    var erroConexao by mutableStateOf<String?>(null)
        private set

    var localizacao by mutableStateOf<Ponto?>(null)
        private set

    var resultado by mutableStateOf<TriagemResultado?>(null)
        private set
    var triando by mutableStateOf(false)
        private set
    var erroTriagem by mutableStateOf<String?>(null)
        private set

    var unidades by mutableStateOf<UnidadesResposta?>(null)
        private set
    var filtroTipos by mutableStateOf(setOf<String>())
        private set
    var carregandoUnidades by mutableStateOf(false)
        private set

    var previsoes by mutableStateOf<ResumoPrevisoes?>(null)
        private set
    var carregandoPrevisoes by mutableStateOf(false)
        private set
    var erroPrevisoes by mutableStateOf<String?>(null)
        private set

    var dadosUteis by mutableStateOf<DadosUteis?>(null)
        private set

    init {
        carregarTudo()
        // Atualiza a ocupação das unidades a cada 30 segundos.
        viewModelScope.launch {
            while (true) {
                delay(30_000)
                atualizarUnidades(silencioso = true)
            }
        }
    }

    fun carregarTudo() {
        viewModelScope.launch {
            try {
                config = api.config()
                erroConexao = null
            } catch (e: Exception) {
                erroConexao = "Não foi possível conectar ao servidor em $apiUrl (${e.message}). " +
                    "Verifique se o backend está rodando no notebook."
            }
            atualizarUnidades()
            runCatching { dadosUteis = api.dadosUteis() }
        }
        carregarPrevisoes()
    }

    fun definirApiUrl(url: String) {
        apiUrl = url.trim()
        prefs.edit().putString("api_url", apiUrl).apply()
        api = Api(apiUrl)
        carregarTudo()
    }

    fun definirLocalizacao(lat: Double, lon: Double) {
        localizacao = Ponto(lat, lon)
        atualizarUnidades(silencioso = true)
    }

    fun alternarFiltro(tipo: String) {
        filtroTipos = if (tipo in filtroTipos) filtroTipos - tipo else filtroTipos + tipo
        atualizarUnidades()
    }

    fun atualizarUnidades(silencioso: Boolean = false) {
        viewModelScope.launch {
            if (!silencioso) carregandoUnidades = true
            try {
                val ponto = localizacao ?: config?.centroMapa
                unidades = api.unidades(ponto?.lat, ponto?.lon, filtroTipos)
            } catch (e: Exception) {
                // mantém a última leitura; o aviso de conexão já aparece no topo
            } finally {
                carregandoUnidades = false
            }
        }
    }

    fun carregarPrevisoes() {
        viewModelScope.launch {
            carregandoPrevisoes = true
            erroPrevisoes = null
            try {
                previsoes = api.previsoes(8)
            } catch (e: Exception) {
                erroPrevisoes = "Falha ao carregar previsões: ${e.message}"
            } finally {
                carregandoPrevisoes = false
            }
        }
    }

    fun triar(entrada: TriagemEntrada) {
        viewModelScope.launch {
            triando = true
            erroTriagem = null
            try {
                val ponto = localizacao ?: config?.centroMapa
                resultado = api.triagem(entrada.copy(lat = ponto?.lat, lon = ponto?.lon))
            } catch (e: Exception) {
                resultado = null
                erroTriagem = if (entrada.sintomas.any { it in SINTOMAS_ALARME_OFFLINE }) {
                    "Sem conexão com o servidor. Você marcou um sinal de alarme: LIGUE 192 (SAMU) " +
                        "ou procure o pronto-socorro imediatamente."
                } else {
                    "Sem conexão com o servidor (${e.message}). Se os sintomas forem graves, ligue 192."
                }
            } finally {
                triando = false
            }
        }
    }

    fun limparTriagem() {
        resultado = null
        erroTriagem = null
    }
}
