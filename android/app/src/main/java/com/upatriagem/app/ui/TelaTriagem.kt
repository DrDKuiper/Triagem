package com.upatriagem.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.upatriagem.app.AppViewModel
import com.upatriagem.app.data.SinaisVitais
import com.upatriagem.app.data.TriagemEntrada
import com.upatriagem.app.data.TriagemResultado

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TelaTriagem(vm: AppViewModel, irParaUnidades: () -> Unit) {
    val resultado = vm.resultado
    if (resultado != null) {
        ResultadoTriagem(resultado, onNova = vm::limparTriagem, irParaUnidades = irParaUnidades)
        return
    }

    var idade by rememberSaveable { mutableStateOf("") }
    var gestante by rememberSaveable { mutableStateOf(false) }
    var relato by rememberSaveable { mutableStateOf("") }
    var sintomas by rememberSaveable { mutableStateOf(listOf<String>()) }
    var comorbidades by rememberSaveable { mutableStateOf(listOf<String>()) }
    var dias by rememberSaveable { mutableStateOf("1") }
    var dor by rememberSaveable { mutableFloatStateOf(0f) }
    var temperatura by rememberSaveable { mutableStateOf("") }
    var saturacao by rememberSaveable { mutableStateOf("") }
    var consentimento by rememberSaveable { mutableStateOf(false) }

    val config = vm.config
    val idadeInt = idade.toIntOrNull()

    Column(
        Modifier.verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Triagem inteligente", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text(
            "Responda para saber se você deve ir à UPA, à UBS (posto) ou se pode se cuidar em casa." +
                (config?.municipio?.let { " — $it" } ?: ""),
            style = MaterialTheme.typography.bodyMedium,
        )

        OutlinedTextField(
            value = idade,
            onValueChange = { idade = it.filter(Char::isDigit).take(3) },
            label = { Text("Idade (anos)") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            Switch(checked = gestante, onCheckedChange = { gestante = it })
            Spacer(Modifier.size(8.dp))
            Text("Gestante")
        }

        OutlinedTextField(
            value = relato,
            onValueChange = { relato = it.take(2000) },
            label = { Text("Descreva o que está sentindo") },
            placeholder = { Text("Ex.: febre desde ontem, dor no corpo e atrás dos olhos") },
            minLines = 3,
            modifier = Modifier.fillMaxWidth(),
        )

        Text("Ou marque os sintomas:", fontWeight = FontWeight.SemiBold)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            config?.sintomas?.forEach { s ->
                val marcado = s.codigo in sintomas
                FilterChip(
                    selected = marcado,
                    onClick = { sintomas = if (marcado) sintomas - s.codigo else sintomas + s.codigo },
                    label = { Text(s.rotulo) },
                )
            }
        }

        OutlinedTextField(
            value = dias,
            onValueChange = { dias = it.filter(Char::isDigit).take(3) },
            label = { Text("Há quantos dias?") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )

        Text("Intensidade da dor: ${dor.toInt()}/10", fontWeight = FontWeight.SemiBold)
        Slider(value = dor, onValueChange = { dor = it }, valueRange = 0f..10f, steps = 9)

        Text("Doenças pré-existentes:", fontWeight = FontWeight.SemiBold)
        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            config?.comorbidades?.forEach { c ->
                val marcado = c.codigo in comorbidades
                FilterChip(
                    selected = marcado,
                    onClick = { comorbidades = if (marcado) comorbidades - c.codigo else comorbidades + c.codigo },
                    label = { Text(c.rotulo) },
                )
            }
        }

        Text("Se tiver termômetro ou oxímetro (opcional):", fontWeight = FontWeight.SemiBold)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                value = temperatura,
                onValueChange = { temperatura = it.replace(',', '.').filter { c -> c.isDigit() || c == '.' }.take(4) },
                label = { Text("Temperatura °C") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
            OutlinedTextField(
                value = saturacao,
                onValueChange = { saturacao = it.filter(Char::isDigit).take(3) },
                label = { Text("Saturação %") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                singleLine = true,
                modifier = Modifier.weight(1f),
            )
        }

        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(checked = consentimento, onCheckedChange = { consentimento = it })
            Text(
                "Autorizo o envio desta triagem ao prontuário da unidade (LGPD).",
                style = MaterialTheme.typography.bodySmall,
            )
        }

        vm.erroTriagem?.let {
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                Text(it, Modifier.padding(12.dp), fontWeight = FontWeight.SemiBold)
            }
        }

        Button(
            onClick = {
                vm.triar(
                    TriagemEntrada(
                        idade = idadeInt ?: 0,
                        gestante = gestante,
                        relato = relato,
                        sintomas = sintomas,
                        diasSintomas = dias.toIntOrNull() ?: 1,
                        intensidadeDor = dor.toInt(),
                        comorbidades = comorbidades,
                        sinaisVitais = SinaisVitais(
                            temperatura = temperatura.toDoubleOrNull()?.takeIf { it in 30.0..45.0 },
                            saturacao = saturacao.toIntOrNull()?.takeIf { it in 50..100 },
                        ),
                        consentimentoLgpd = consentimento,
                    )
                )
            },
            enabled = !vm.triando && idadeInt != null && idadeInt <= 120 &&
                (relato.isNotBlank() || sintomas.isNotEmpty()),
            modifier = Modifier.fillMaxWidth().height(52.dp),
        ) {
            if (vm.triando) CircularProgressIndicator(Modifier.size(24.dp)) else Text("Avaliar")
        }
        Text(
            "Em caso de emergência, não espere: ligue 192 (SAMU).",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.error,
        )
    }
}

@Composable
private fun ResultadoTriagem(r: TriagemResultado, onNova: () -> Unit, irParaUnidades: () -> Unit) {
    val contexto = LocalContext.current
    val cor = corPrioridade(r.prioridade)
    Column(
        Modifier.verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Column(
            Modifier.fillMaxWidth().background(cor, MaterialTheme.shapes.medium).padding(16.dp)
        ) {
            Text(r.prioridade.uppercase(), color = textoSobre(cor), style = MaterialTheme.typography.labelLarge)
            Text(r.titulo, color = textoSobre(cor), style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            r.tempoAlvoMin?.takeIf { it > 0 }?.let {
                Text("Procure atendimento em até $it min", color = textoSobre(cor))
            }
        }
        Text(r.orientacao, style = MaterialTheme.typography.titleMedium)

        if (r.destino == "SAMU") {
            Button(onClick = { ligar(contexto, "192") }, modifier = Modifier.fillMaxWidth().height(56.dp)) {
                Text("LIGAR 192 — SAMU", fontWeight = FontWeight.Bold)
            }
        }

        if (r.sintomasIdentificados.isNotEmpty()) {
            Text("Sintomas considerados: " + r.sintomasIdentificados.joinToString(", "))
        }
        r.agravoProvavel?.let { Text("Possível quadro: $it", fontWeight = FontWeight.SemiBold) }
        Text("Por quê:", fontWeight = FontWeight.SemiBold)
        r.motivos.forEach { Text("• $it") }

        if (r.unidadesSugeridas.isNotEmpty()) {
            HorizontalDivider()
            Text("Unidades sugeridas (menor tempo total)", style = MaterialTheme.typography.titleMedium)
            r.unidadesSugeridas.forEach { CartaoUnidade(it) }
            OutlinedButton(onClick = irParaUnidades, modifier = Modifier.fillMaxWidth()) { Text("Ver todas no mapa") }
        }

        Text(
            "Análise: regras clínicas + IA (${r.fonteExtracao})" +
                if (r.registradoProntuario) " • enviada ao prontuário" else "",
            style = MaterialTheme.typography.bodySmall,
        )
        Text(r.aviso, style = MaterialTheme.typography.bodySmall)
        Button(onClick = onNova, modifier = Modifier.fillMaxWidth()) { Text("Nova triagem") }
    }
}
