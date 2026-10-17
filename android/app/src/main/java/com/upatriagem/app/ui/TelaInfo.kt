package com.upatriagem.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.upatriagem.app.AppViewModel

@Composable
fun TelaInfo(vm: AppViewModel) {
    val contexto = LocalContext.current
    val dados = vm.dadosUteis
    var url by rememberSaveable { mutableStateOf(vm.apiUrl) }

    Column(
        Modifier.verticalScroll(rememberScrollState()).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("Dados úteis", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)

        dados?.telefones?.forEach { t ->
            Card(Modifier.fillMaxWidth()) {
                Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("${t.nome} — ${t.numero}", fontWeight = FontWeight.Bold)
                        Text(t.descricao, style = MaterialTheme.typography.bodySmall)
                    }
                    IconButton(onClick = { ligar(contexto, t.numero) }) { Icon(Icons.Filled.Call, "Ligar ${t.numero}") }
                }
            }
        }

        dados?.let { d ->
            Text("Onde procurar atendimento", style = MaterialTheme.typography.titleMedium)
            d.quandoProcurar.forEach { (local, quando) ->
                Text(local, fontWeight = FontWeight.SemiBold)
                Text(quando, style = MaterialTheme.typography.bodyMedium)
            }
            Text("Leve com você", style = MaterialTheme.typography.titleMedium)
            d.documentos.forEach { Text("• $it") }
            Text("Dicas de saúde", style = MaterialTheme.typography.titleMedium)
            d.dicas.forEach { Text("• $it") }
        }

        HorizontalDivider()
        Text("Servidor", style = MaterialTheme.typography.titleMedium)
        Text(
            "Emulador: http://10.0.2.2:8000 (o notebook). Celular físico na mesma rede Wi-Fi: " +
                "http://IP-DO-NOTEBOOK:8000.",
            style = MaterialTheme.typography.bodySmall,
        )
        OutlinedTextField(
            value = url,
            onValueChange = { url = it },
            label = { Text("Endereço do backend") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        Button(onClick = { vm.definirApiUrl(url) }, modifier = Modifier.fillMaxWidth()) { Text("Salvar e reconectar") }
        Text(
            "Este aplicativo orienta e não substitui a avaliação de um profissional de saúde. " +
                "Os dados de unidades são de demonstração até a integração com o prontuário/CNES do município.",
            style = MaterialTheme.typography.bodySmall,
        )
    }
}
