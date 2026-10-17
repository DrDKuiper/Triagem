package com.upatriagem.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.upatriagem.app.AppViewModel
import com.upatriagem.app.data.PrevisaoAgravo

private const val SEMANAS_HISTORICO = 26

@Composable
fun TelaPrevisoes(vm: AppViewModel) {
    val resumo = vm.previsoes
    LazyColumn(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        item {
            Column {
                Row(Modifier.padding(start = 16.dp, end = 8.dp, top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Previsão de doenças", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                        Text(
                            "Modelo de ML (gradient boosting) com sazonalidade, clima e histórico de casos.",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    IconButton(onClick = vm::carregarPrevisoes) { Icon(Icons.Filled.Refresh, "Atualizar") }
                }
                if (vm.carregandoPrevisoes) {
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                    Text("Treinando modelos…", Modifier.padding(16.dp), style = MaterialTheme.typography.bodySmall)
                }
                vm.erroPrevisoes?.let { Text(it, Modifier.padding(16.dp), color = MaterialTheme.colorScheme.error) }
            }
        }
        if (resumo != null && resumo.alertas.isNotEmpty()) {
            item {
                Card(
                    Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                    colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF3E0)),
                ) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Alertas para as próximas ${resumo.horizonteSemanas} semanas", fontWeight = FontWeight.Bold, color = Color.Black)
                        resumo.alertas.forEach { a ->
                            Text(
                                "• ${a.nome}: nível ${a.nivel} — pico previsto de ${a.picoPrevisto.casos} casos/semana em ${dataCurta(a.picoPrevisto.semana)}",
                                color = Color.Black,
                            )
                        }
                    }
                }
            }
        }
        items(resumo?.agravos.orEmpty(), key = { it.agravo }) { a ->
            CartaoAgravo(a, Modifier.padding(horizontal = 16.dp))
        }
        item {
            Column(Modifier.padding(16.dp)) {
                Text("Como ler", fontWeight = FontWeight.SemiBold)
                Legenda(Color(0xFF388E3C), "Abaixo da mediana histórica")
                Legenda(Color(0xFFFBC02D), "Esperado (até o 3º quartil)")
                Legenda(Color(0xFFF57C00), "Alerta (acima do esperado)")
                Legenda(Color(0xFFD32F2F), "Epidemia (acima do limite superior)")
                Text(
                    "Faixa sombreada: canal endêmico (anos anteriores). Linha tracejada: previsão; área clara: intervalo de 80%.",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

@Composable
private fun Legenda(cor: Color, texto: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(10.dp).background(cor, CircleShape))
        Spacer(Modifier.size(6.dp))
        Text(texto, style = MaterialTheme.typography.bodySmall)
    }
}

private fun dataCurta(iso: String): String = iso.split("-").let { if (it.size == 3) "${it[2]}/${it[1]}" else iso }

@Composable
private fun CartaoAgravo(a: PrevisaoAgravo, modifier: Modifier) {
    Card(modifier.fillMaxWidth(), elevation = CardDefaults.cardElevation(2.dp)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(a.nome, fontWeight = FontWeight.Bold, modifier = Modifier.weight(1f))
                val cor = corNivel(a.nivelAtual)
                Text(
                    a.nivelAtual.uppercase(),
                    color = textoSobre(cor),
                    style = MaterialTheme.typography.labelMedium,
                    modifier = Modifier.background(cor, MaterialTheme.shapes.small).padding(horizontal = 8.dp, vertical = 2.dp),
                )
            }
            val atual = a.observado.lastOrNull()?.casos ?: 0
            val sinal = if (a.tendenciaPct >= 0) "+" else ""
            Text("$atual casos na última semana • tendência $sinal${"%.0f".format(a.tendenciaPct)}% em 4 semanas")
            Grafico(a, Modifier.fillMaxWidth().height(140.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                a.previsao.take(4).forEach { p ->
                    val cor = corNivel(p.nivel)
                    Column(
                        Modifier.weight(1f).background(cor.copy(alpha = 0.18f), MaterialTheme.shapes.small).padding(6.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(dataCurta(p.semana), style = MaterialTheme.typography.labelSmall)
                        Text("${p.previsto}", fontWeight = FontWeight.Bold)
                        Text("${p.minimo}–${p.maximo}", style = MaterialTheme.typography.labelSmall)
                    }
                }
            }
            a.erroBacktestPct?.let {
                Text("Erro médio do modelo nas últimas 26 semanas: ${"%.0f".format(it)}%", style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun Grafico(a: PrevisaoAgravo, modifier: Modifier) {
    val obs = a.observado.takeLast(SEMANAS_HISTORICO)
    val prev = a.previsao
    val corLinha = MaterialTheme.colorScheme.primary
    val corPrev = MaterialTheme.colorScheme.secondary
    val corCanal = Color(0xFF9E9E9E)
    Canvas(modifier) {
        val n = obs.size + prev.size
        if (obs.isEmpty() || n < 2) return@Canvas
        val maximo = (obs.map { maxOf(it.casos, it.canal.limiteSuperior) } +
            prev.map { maxOf(it.maximo, it.canal.limiteSuperior) }).maxOrNull()?.coerceAtLeast(1) ?: 1
        fun x(i: Int) = i * size.width / (n - 1)
        fun y(v: Int) = size.height - v.toFloat() / maximo * size.height * 0.95f

        // Canal endêmico (entre mediana e limite superior)
        val canais = obs.map { it.canal } + prev.map { it.canal }
        val faixa = Path().apply {
            canais.forEachIndexed { i, c -> if (i == 0) moveTo(x(i), y(c.limiteSuperior)) else lineTo(x(i), y(c.limiteSuperior)) }
            for (i in canais.indices.reversed()) lineTo(x(i), y(canais[i].mediana))
            close()
        }
        drawPath(faixa, corCanal.copy(alpha = 0.25f))

        // Intervalo da previsão
        val base = obs.size - 1
        val intervalo = Path().apply {
            moveTo(x(base), y(obs.last().casos))
            prev.forEachIndexed { i, p -> lineTo(x(base + i + 1), y(p.maximo)) }
            for (i in prev.indices.reversed()) lineTo(x(base + i + 1), y(prev[i].minimo))
            close()
        }
        drawPath(intervalo, corPrev.copy(alpha = 0.2f))

        val linhaObs = Path().apply {
            obs.forEachIndexed { i, o -> if (i == 0) moveTo(x(i), y(o.casos)) else lineTo(x(i), y(o.casos)) }
        }
        drawPath(linhaObs, corLinha, style = Stroke(width = 4f))

        val linhaPrev = Path().apply {
            moveTo(x(base), y(obs.last().casos))
            prev.forEachIndexed { i, p -> lineTo(x(base + i + 1), y(p.previsto)) }
        }
        drawPath(linhaPrev, corPrev, style = Stroke(width = 4f, pathEffect = PathEffect.dashPathEffect(floatArrayOf(12f, 8f))))
        drawLine(Color.Gray, Offset(x(base), 0f), Offset(x(base), size.height), strokeWidth = 1f)
    }
}
