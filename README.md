# HealthFlow — Lençóis Paulista (SP)

Aplicativo para reduzir filas desnecessárias na UPA e nas UBS (postos de saúde):

- **Triagem com IA**: o paciente descreve o que sente (texto livre ou marcando sintomas) e recebe a classificação de risco (cores do Protocolo de Manchester) e para onde ir: SAMU 192, UPA, UBS ou cuidado em casa.
- **Atendimentos em andamento**: tela com cada unidade ("UPA — 25 em atendimento"), fila, tempo estimado de espera, lotação, mapa e geolocalização. As unidades são ordenadas pelo menor tempo total (deslocamento + espera).
- **Integração com o prontuário local** via HL7 FHIR R4 (padrão da RNDS), com modo simulado para demonstração.
- **Análise preditiva (ML)** de síndrome gripal, COVID-19, dengue, gastroenterite e VSR, com canal endêmico e alertas.
- **Dados úteis**: telefones de emergência, onde procurar atendimento, documentos, dicas de saúde.

```
┌──────────────────────┐   HTTP/JSON   ┌───────────────────────────┐   FHIR R4   ┌──────────────┐
│ App Android (Kotlin) │ ────────────▶ │ Backend Python (FastAPI)  │ ──────────▶ │ Prontuário   │
│ emulador ou celular  │               │ regras + ML + previsões   │             │ local (PEP)  │
└──────────────────────┘               └───────────────────────────┘             └──────────────┘
```

## Experimente sem instalar nada

- **Página web**: <https://drdkuiper.github.io/Triagem/>
- **App Android (APK)**: <https://github.com/DrDKuiper/triagem/releases/latest/download/HealthFlow.apk>. No celular, permita instalar apps de fontes desconhecidas.

Nas duas versões o backend Python roda **dentro do navegador/celular** com o [Pyodide](https://pyodide.org) (numpy, pandas, scikit-learn e FastAPI compilados para WebAssembly), sem servidor. Os dados são os fictícios do modo simulado e ficam só na memória do aparelho. Na primeira abertura são baixados cerca de 40 MB e é preciso internet; depois o navegador guarda os arquivos em cache.

Como funciona:

- `scripts/construir_site.py` gera o site estático: `app/web/` + `web/offline.js` + o pacote `app/` compactado em `web/backend.zip`.
- `app/web/offline-worker.js` carrega o Pyodide num Web Worker e atende as chamadas da página por `app/offline.py`, que executa as mesmas funções das rotas de `app/main.py`.
- O módulo Android `android/web` (pacote `com.healthflow.app`) empacota esse site e o abre em tela cheia, sem a moldura de celular e o painel lateral da página (`construir_site.py --app`). O módulo `android/app` continua sendo o app nativo em Kotlin que usa o backend no notebook.
- O workflow `.github/workflows/publicar.yml` roda os testes, testa o site no navegador e compila o APK. No `main`, ele também publica a página no GitHub Pages e o APK na release `app-android`.

**Assinatura do APK**: sem configuração, o APK é assinado com a chave de debug do GitHub Actions, que muda a cada execução. Para instalar uma versão nova, é preciso desinstalar a anterior. Para manter a mesma assinatura, crie uma chave (`keytool -genkeypair -keystore upatriagem.jks -alias upatriagem -keyalg RSA -validity 10000`) e cadastre em *Settings → Secrets and variables → Actions* os secrets `ANDROID_KEYSTORE_BASE64` (o arquivo `.jks` em base64) e `ANDROID_KEYSTORE_SENHA`.

## Como rodar no notebook

### 1. Backend (Python 3.10+)

Windows: dê dois cliques em `iniciar_backend.bat` (ou rode no terminal).
Linux/macOS: `./iniciar_backend.sh`.

Na primeira vez ele cria um ambiente virtual e instala as dependências. Depois, abra
<http://localhost:8000/docs> para ver e testar a API.

> Na primeira consulta de previsões os modelos são treinados (alguns segundos).

### 2. Versão web (sem Android Studio)

Com o backend rodando, abra <http://localhost:8000>. No computador, o app aparece dentro de uma moldura de celular, com as mesmas 4 telas do Android (Triagem, Unidades, Previsões e Info). Num celular de verdade, ele ocupa a tela toda.

Os arquivos ficam em `app/web/` (HTML, CSS e JavaScript puros, sem build). A versão estática (Pages/APK) é descrita em "Experimente sem instalar nada". O mapa usa Leaflet com OpenStreetMap.

Para testar num celular da mesma rede Wi-Fi, abra `http://IP-DO-NOTEBOOK:8000`. Para publicar online, basta hospedar o backend (ex.: Render, Railway, Fly.io ou um servidor da prefeitura) com o comando `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. A geolocalização do navegador só funciona com HTTPS (ou em `localhost`); sem ela, o app usa o centro do município.

### 3. App Android (Android Studio)

1. Abra o Android Studio → **Open** → selecione a pasta `android` do projeto.
2. Aguarde o *Gradle Sync* (baixa as dependências na primeira vez).
3. Crie um emulador em **Device Manager** (ex.: Pixel, API 34) e clique em **Run ▶**.
4. O app acessa o backend em `http://10.0.2.2:8000`, que é o próprio notebook visto de dentro do emulador.

**Localização no emulador**: em *Extended controls (⋯) → Location*, busque "Lençóis Paulista" e clique em *Set location*. Sem localização, o app usa o centro do município.

**Celular físico**: conecte-o na mesma rede Wi-Fi do notebook, descubra o IP do notebook (`ipconfig` no Windows) e, na aba **Info** do app, troque o endereço do servidor para `http://IP-DO-NOTEBOOK:8000`. Pode ser preciso liberar a porta 8000 no firewall do Windows.

### Testes do backend

```
.venv\Scripts\activate      (Windows)   |   . .venv/bin/activate   (Linux/macOS)
python -m pytest -q
```

## Como a triagem funciona

1. **Extração de sintomas** do texto livre: por palavras-chave em português (com tratamento de negação, ex.: "sem falta de ar") ou, opcionalmente, pelo **Claude** (`TRIAGEM_USAR_LLM=1` + `ANTHROPIC_API_KEY`). O LLM só estrutura o relato; ele não decide o risco.
2. **Regras clínicas determinísticas** (sinais de alarme: AVC, dor no peito, falta de ar, saturação baixa, convulsão...).
3. **Modelo de ML** (Random Forest) que estima a gravidade e o quadro provável pela combinação de sintomas, idade, comorbidades e sinais vitais.
4. **Resultado = o nível mais grave** entre regras e ML: a IA pode subir a prioridade, nunca baixar um sinal de alarme.
5. Indica as 3 unidades mais adequadas (UPA/PS para urgências, UBS para casos leves) e, com consentimento (LGPD), envia a pré-triagem ao prontuário.

## Cartão Cidadão e análise ambiental do bairro

A primeira tela da versão web pede o número do **Cartão Cidadão**. A consulta (`GET /api/cidadao/{cartao}`) devolve:

- **Cadastro e resumo do prontuário**: idade, sexo, gestação, doenças, medicamentos, alergias, vacinas, últimas consultas, endereço e UBS de referência.
- **Análise ambiental do bairro**: infestação do Aedes (LIRAa) e casos de dengue, qualidade do ar (MP2,5, piora na seca perto de canaviais), risco de alagamento/leptospirose perto do Rio Lençóis e escorpiões. O clima e os casos vêm do histórico semanal do prontuário.
- **Alertas personalizados**, que cruzam o bairro com o perfil (ex.: idosa diabética em bairro com dengue; criança asmática com ar ruim).

Na triagem, o cartão completa doenças, gestação, CNS e endereço. Sem GPS, as unidades são ordenadas a partir da casa do cidadão. O resultado traz as **condições do bairro** ligadas aos sintomas (ex.: febre + dor no corpo em bairro com Aedes indica suspeita de dengue). O contexto ambiental orienta, mas **não altera a classificação de risco clínica**.

**Base de teste**: `app/cidadao/cadastro.py` gera 40 moradores **fictícios** de bairros de Lençóis Paulista (cartões `10000001` a `10000040`). Os 11 primeiros têm perfis pensados para testes (idosa diabética, criança asmática, gestante, criança com TEA, idosa acamada, cadeirante...) e aparecem na tela inicial (`GET /api/cidadao/exemplos`). Bairros e fatores ambientais ficam em `app/cidadao/bairros.py`. Para a integração real, implemente `CadastroCidadao` consultando o sistema do Cartão Cidadão e o prontuário.

### Para onde a triagem manda

- **O hospital nunca é indicado.** Emergência (vermelho): ligar 192 (SAMU). Urgência (laranja/amarelo): **UPA**. Casos leves (verde/azul): **ESF/UBS do bairro** do Cartão Cidadão. Sem cartão, vai para a unidade mais próxima. Se a unidade estiver fechada, o caso verde também recebe a UPA como alternativa.
- **Visitante** (não mora em Lençóis Paulista, sem Cartão Cidadão): a tela inicial tem a opção "Não moro em Lençóis Paulista". A triagem informa que o SUS atende todos e quais documentos levar.

### Acessibilidade, acompanhante e ambulância

O cadastro e o formulário trazem: cadeirante, dificuldade motora, acamado, autismo (TEA), deficiência visual, auditiva e intelectual, e se a pessoa **precisa de ambulância**. O resultado mostra:

- **Acompanhante**: obrigatório para menores de 18 anos (ECA); recomendado com 80+ anos, TEA, acamado ou dificuldade motora; direito da pessoa idosa (60+) e da gestante.
- **Como ir**: SAMU 192 quando precisa de ambulância e o caso é urgente; visita domiciliar da ESF quando não é urgente; transporte adaptado para cadeirantes.
- **Atendimento prioritário** (Lei 10.048/2000, Lei 12.764/2012 para TEA, Estatuto da Pessoa Idosa).

Regras em `app/triagem/acessibilidade.py`.

### Unidades e horários reais

`app/unidades/catalogo.py` traz as 11 unidades de Atenção Básica (ESF/UBS) e a UPA, com nome, endereço e telefone do site da Prefeitura (Secretaria de Saúde > Unidades de Atendimento). Os horários vêm da Carta de Serviços:

- **Atenção Básica**: seg a qui 7h–22h, sex 7h–20h, sáb 7h–13h.
- **UPA**: 24h.

O status "aberta/fechada" segue esses horários. As coordenadas são aproximadas (rua no OpenStreetMap) e precisam ser confirmadas no CNES.

> ⚠️ Em produção, a consulta pelo cartão expõe dados de saúde. Ela precisa de autenticação (ex.: senha/PIN do Cartão Cidadão, gov.br ou código por SMS), HTTPS e limite de tentativas. Hoje basta saber o número.

## Previsão de doenças

Para cada agravo, um *gradient boosting* com regressão quantílica (10%, 50%, 90%) usa casos das semanas anteriores, sazonalidade e clima (temperatura, umidade e chuva, com defasagem; a chuva é o principal fator para a dengue). O nível de alerta segue o **diagrama de controle (canal endêmico)**: mediana, 3º quartil e limite superior (média + 1,96 dp) da mesma semana epidemiológica nos anos anteriores. Os modelos são retreinados a cada 6 horas com o histórico do prontuário.

## Integração com o prontuário

| Variável | Descrição |
|---|---|
| `PRONTUARIO_BACKEND` | `mock` (padrão, dados simulados) ou `fhir` |
| `FHIR_BASE_URL` | URL base do servidor FHIR R4 do prontuário |
| `FHIR_TOKEN` | Token Bearer (opcional) |
| `TRIAGEM_USAR_LLM` | `1` para extrair sintomas com o Claude |
| `MUNICIPIO`, `POPULACAO`, `MAPA_LAT`, `MAPA_LON` | Município atendido (padrão: Lençóis Paulista, 70 mil hab.) |

Mapeamento FHIR: ocupação = `Encounter` (`in-progress` = em atendimento, `arrived,triaged` = aguardando) por `Location` (CNES da unidade); triagem enviada como `Observation` (category `survey`, paciente identificado pelo CNS); histórico de agravos = `Condition` agrupada por CID-10. Para outro formato de prontuário, implemente `ProntuarioAdapter` em `app/prontuario/`.

## ⚠️ Antes de usar com pacientes reais

- **Unidades**: nomes, endereços, telefones e horários em `app/unidades/catalogo.py` vêm do site da Prefeitura (consultado em 17/10/2026). As coordenadas são aproximadas. Confirme com a Secretaria Municipal de Saúde/CNES, preencha o código CNES e revise se alguma unidade tem horário próprio (a Carta de Serviços publica um horário único para a Atenção Básica).
- **Territórios**: o bairro → unidade de referência em `app/cidadao/bairros.py` é aproximado. Use a territorialização oficial das equipes de Saúde da Família.
- **Dados epidemiológicos e de ocupação** são simulados até a conexão com o prontuário.
- **Modelos de ML** foram treinados com dados sintéticos. Retreine com triagens reais classificadas por profissionais (`ModeloTriagem.treinar`) e valide clinicamente as regras com a equipe médica.
- O app é uma ferramenta de orientação e **não substitui avaliação profissional**.
- Em produção, publique o backend com HTTPS e remova a liberação de HTTP em `android/app/src/main/res/xml/network_security_config.xml`.
