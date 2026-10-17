package com.upatriagem.app.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
data class ItemCatalogo(val codigo: String, val rotulo: String)

@Serializable
data class Ponto(val lat: Double, val lon: Double)

@Serializable
data class ConfigApp(
    val municipio: String = "",
    @SerialName("centro_mapa") val centroMapa: Ponto,
    val sintomas: List<ItemCatalogo>,
    val comorbidades: List<ItemCatalogo>,
)

@Serializable
data class SinaisVitais(
    val temperatura: Double? = null,
    val saturacao: Int? = null,
)

@Serializable
data class TriagemEntrada(
    val idade: Int,
    val gestante: Boolean = false,
    val relato: String = "",
    val sintomas: List<String> = emptyList(),
    @SerialName("dias_sintomas") val diasSintomas: Int = 1,
    @SerialName("intensidade_dor") val intensidadeDor: Int = 0,
    val comorbidades: List<String> = emptyList(),
    @SerialName("sinais_vitais") val sinaisVitais: SinaisVitais = SinaisVitais(),
    val lat: Double? = null,
    val lon: Double? = null,
    @SerialName("consentimento_lgpd") val consentimentoLgpd: Boolean = false,
)

@Serializable
data class Unidade(
    val id: String,
    val nome: String,
    val tipo: String,
    val endereco: String = "",
    val bairro: String = "",
    val telefone: String = "",
    val lat: Double,
    val lon: Double,
    val horario: String = "",
    @SerialName("aberta_24h") val aberta24h: Boolean = false,
    val servicos: List<String> = emptyList(),
    @SerialName("em_atendimento") val emAtendimento: Int? = null,
    val aguardando: Int? = null,
    @SerialName("espera_estimada_min") val esperaMin: Int? = null,
    val lotacao: String = "",
    val funcionando: Boolean? = null,
    @SerialName("distancia_km") val distanciaKm: Double? = null,
    @SerialName("deslocamento_min") val deslocamentoMin: Int? = null,
    @SerialName("dados_confirmados") val dadosConfirmados: Boolean = false,
)

@Serializable
data class UnidadesResposta(
    val unidades: List<Unidade>,
    @SerialName("em_atendimento_por_tipo") val emAtendimentoPorTipo: Map<String, Int>,
)

@Serializable
data class TriagemResultado(
    val id: String,
    val prioridade: String,
    val nivel: Int,
    val titulo: String,
    val orientacao: String,
    val destino: String,
    @SerialName("tempo_alvo_min") val tempoAlvoMin: Int? = null,
    @SerialName("sintomas_identificados") val sintomasIdentificados: List<String> = emptyList(),
    @SerialName("sinais_alarme") val sinaisAlarme: List<String> = emptyList(),
    val motivos: List<String> = emptyList(),
    @SerialName("probabilidades_ml") val probabilidadesMl: Map<String, Double> = emptyMap(),
    @SerialName("agravo_provavel") val agravoProvavel: String? = null,
    @SerialName("fonte_extracao") val fonteExtracao: String = "",
    @SerialName("unidades_sugeridas") val unidadesSugeridas: List<Unidade> = emptyList(),
    @SerialName("registrado_prontuario") val registradoProntuario: Boolean = false,
    val aviso: String = "",
)

@Serializable
data class Canal(
    val q1: Int,
    val mediana: Int,
    val q3: Int,
    @SerialName("limite_superior") val limiteSuperior: Int,
)

@Serializable
data class Observado(val semana: String, val casos: Int, val canal: Canal)

@Serializable
data class PontoPrevisao(
    val semana: String,
    @SerialName("semana_epidemiologica") val semanaEpidemiologica: Int,
    val previsto: Int,
    val minimo: Int,
    val maximo: Int,
    val nivel: String,
    val canal: Canal,
)

@Serializable
data class Pico(val semana: String, val casos: Int)

@Serializable
data class PrevisaoAgravo(
    val agravo: String,
    val nome: String,
    val observado: List<Observado>,
    val previsao: List<PontoPrevisao>,
    @SerialName("tendencia_pct") val tendenciaPct: Double,
    @SerialName("nivel_atual") val nivelAtual: String,
    @SerialName("pico_previsto") val picoPrevisto: Pico,
    @SerialName("erro_backtest_pct") val erroBacktestPct: Double? = null,
)

@Serializable
data class Alerta(
    val agravo: String,
    val nome: String,
    val nivel: String,
    @SerialName("tendencia_pct") val tendenciaPct: Double,
    @SerialName("pico_previsto") val picoPrevisto: Pico,
)

@Serializable
data class ResumoPrevisoes(
    @SerialName("horizonte_semanas") val horizonteSemanas: Int,
    val agravos: List<PrevisaoAgravo>,
    val alertas: List<Alerta>,
)

@Serializable
data class Telefone(val nome: String, val numero: String, val descricao: String)

@Serializable
data class DadosUteis(
    val telefones: List<Telefone>,
    @SerialName("quando_procurar") val quandoProcurar: Map<String, String>,
    val documentos: List<String>,
    val dicas: List<String>,
)
