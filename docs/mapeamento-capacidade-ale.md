# Mapeamento — `02 - CAPACIDADES.xlsx` / aba "Capacidade ALE"

Fonte: `arquivos_apoio/02 - CAPACIDADES.xlsx` (abas "Capacidade ALE" e "Detalhamento Tancagem") + `arquivos_apoio/Despesas.xlsx` (TOP)
Saídas tratadas:
- `dados_tratados/capacidade_ale.csv` (`scripts/extract_capacidade_ale.py`)
- `dados_tratados/capacidade_ale_top.csv` (`scripts/build_capacidade_top.py`)
- `dados_tratados/detalhamento_tancagem.csv` (`scripts/extract_detalhamento_tancagem.py`)
- `dados_tratados/capacidade_por_modelo.csv` (`scripts/build_capacidade_por_modelo.py`)

## Abas do arquivo

| Aba | Conteúdo |
|---|---|
| Resumo | Rankings (top N) por filial: recebimento rodo, venda, expedição rodo |
| **Capacidade ALE** | **Mapeada nesta rodada** — relatório Base x Produto com capacidades e modelo operacional (resumido a 1 modelo por base) |
| Recebimento Rodo - ALE | Capacidade de recebimento rodoviário por base |
| Expedição Rodo - ALE | Capacidade de expedição rodoviária por base |
| **Detalhamento Tancagem** | **Mapeada nesta rodada** (parcial) — tancagem por tanque/produto/armazenador, com Tipo De Espaço, Tipo De Base, Tipo De Operação, Modal. É o grão em que bases "híbridas" aparecem (ver seção abaixo) |
| ATA Tancagem | Manutenções em andamento em tanques (por filial/produto) |
| Movimentação | Médias de movimentação por produto (3/6/12 meses) |
| BD Cap Venda ALE | Base de dados "flat" (fonte de lookup) por Base+Produto, sem coluna de modelo operacional |
| BD Expedição | Capacidade de expedição, CT/hora, horários de funcionamento, participação em Pool |
| BD Descarga | Capacidade de descarga rodoviária por base/armazenador/produto |

## Estrutura da aba "Capacidade ALE"

Grão: **1 linha = 1 Base x Produto**. Cada base tem entre 6 e 8 produtos, mais 1 linha "Total" (produto vazio) usada nos pivôs da aba Resumo — essa linha de total foi descartada no CSV tratado.

Dados começam na linha 5 (linhas 1-4 são título/cabeçalho).

| Coluna origem | Nome no CSV tratado | Descrição |
|---|---|---|
| A | *(descartada)* | Valor auxiliar (= capacidade de venda) usado só na linha de Total, para os pivôs |
| B | *(descartada)* | Código curto da base (ex. "ANDIA") |
| C | *(descartada)* | Chave concatenada Código+Modelo, usada como chave de pivô |
| D | `modelo_operacional` | **Modelo de atuação**: `Terceiros`, `Pool`, `Democrática` ou `Própria` — 1 único modelo por base, não há mistura |
| E | `codigo_base` | Código numérico da base |
| F | `unidade` | Nome da unidade/filial |
| G | `produto` | Produto puro (B100, Diesel A S10, Diesel A S500, Etanol Anidro, Etanol Hidratado, Gasolina A, Diesel Marítimo, Gasolina Premium) |
| I | `tancagem_disponivel_m3` | Tancagem disponível para movimentação (m³) |
| K | `capacidade_recebimento_rodo_m3` | Capacidade mensal de recebimento rodoviário (m³) |
| L | `capacidade_movimentacao_m3` | Capacidade mensal de movimentação (m³) |
| N | `produto_misturado` | Produto final após mistura (ex. Diesel A S10 → Diesel B S10; Gasolina A → Gasolina C; Etanol Hidratado → Álcool) |
| O | `capacidade_venda_m3` | Capacidade mensal de venda (m³), já no produto misturado |
| P | `capacidade_expedicao_rodo_m3` | Capacidade mensal de expedição rodoviária (m³) — só preenchida em parte das linhas |
| Q | `observacoes` | Texto livre, mesclado por base (regras sobre diluição de recebimento rodo e prevalência da capacidade de venda) |
| T | `venda_media_6m_m3` | Venda média mensal (m³) — últimos 6 meses |
| U | `venda_media_12m_m3` | Venda média mensal (m³) — últimos 12 meses |

Colunas S/H/J/M/R e V em diante estão vazias ou duplicam outra coluna (S duplica N).

## Modelos de atuação confirmados na planilha

A coluna D bate exatamente com os 4 modelos descritos:

- **Terceiros** — opera em base/terminal de terceiro
- **Pool** — coproprietário da base
- **Democrática** — base "bico" (cessão de espaço de biocombustível + compra de derivado direto do tanque, sem estoque)
- **Própria** — base 100% própria

43 bases mapeadas, cada uma com exatamente 1 modelo **nesta aba**. Mas isso é uma simplificação: ver seção "Bases híbridas" abaixo — no grão tanque/produto (aba Detalhamento Tancagem), 18 dessas 43 bases operam sob mais de um papel operacional ao mesmo tempo.

## Bases híbridas (mais de uma operação na mesma base)

Duque de Caxias é o exemplo que expôs isso: não são 2 operações, são **3**:

1. **Base própria (uso próprio)** — tancagem própria que a ALE usa.
2. **Cessão de espaço, papel cedente** — dentro dessa mesma base própria, parte da tancagem é cedida a um terceiro que opera junto com a ALE ali (a ALE cede espaço).
3. **Cessão de espaço, papel cessionária** — a ALE também opera na base da Raízen (um congênere), movimentando parte das suas próprias movimentações lá (a ALE recebe/usa espaço de terceiro).

Papéis 2 e 3 são operações opostas (cedente x cessionária) e a aba "Capacidade ALE" não distingue nenhuma delas — resume a base inteira a 1 único `modelo_operacional` ("Própria", nesse caso).

Fonte no grão certo: **Detalhamento Tancagem** (1 linha = 1 alocação de tancagem por Base x Produto x Armazenador x Tipo de Espaço), extraída em `scripts/extract_detalhamento_tancagem.py` → `dados_tratados/detalhamento_tancagem.csv` (362 linhas).

| Coluna origem | Nome no CSV | Descrição |
|---|---|---|
| A | `codigo_base` | Código numérico da base |
| B | `unidade` | Nome da unidade/filial |
| C | `tipo_espaco` | `ESPAÇO ALE - BASE PRÓPRIA`, `ESPAÇO EM TERCEIROS` ou `CARREGAMENTO` |
| D | `modelo` | Modelo operacional **desta alocação** (não da base inteira): `Terceiros`, `Pool`, `Democrática` ou `Própria` |
| E | `tipo_operacao` | `Própria`, `Cessão de Espaço`, `Compra congênere`, `Carregamento`, `Arm Livre Acesso`, `-` |
| F | `produto` | Produto |
| G | `base_armazenador` | Congênere/operador do espaço (ex. VIBRA, ALESAT, RAÍZEN) |
| H | `modal` | `Rodo`, `Duto`, `Ferro`, `Cabotagem`, `-` |
| I-N | `tancagem_operacional_m3`, `lastro_m3`, `tancagem_util_m3`, `reducao_manutencao_m3`, `espaco_cedido_m3`, `tancagem_disponivel_movimentacao_m3` | Composição da tancagem, do bruto até a disponível para movimentação |

`espaco_cedido_m3` (coluna M) só aparece em linhas `ESPAÇO ALE - BASE PRÓPRIA` — é exatamente o papel 2 (cedente): tancagem útil própria que ALE cede a um terceiro dentro da mesma base, reduzindo o que sobra para uso próprio (`tancagem_util_m3` → `tancagem_disponivel_movimentacao_m3`).

`scripts/build_capacidade_por_modelo.py` decompõe cada linha em `papel_operacional` (não só `modelo`) → `dados_tratados/capacidade_por_modelo.csv`:

- `{modelo} (uso próprio)` — ex. "Própria (uso próprio)", "Pool (uso próprio)"
- `Cessão de espaço (cedente)` — sempre que `espaco_cedido_m3 > 0` numa linha própria/pool
- `Cessão de espaço (cessionária) - {modelo}` — linhas `ESPAÇO EM TERCEIROS` (Terceiros ou Democrática)

Resultado: **18 das 43 bases são híbridas** (têm mais de 1 papel operacional):

| Base | Papéis presentes (m³) |
|---|---|
| Duque de Caxias | Própria uso próprio (8.289) + cedente (750) + cessionária-Terceiros (650) |
| Betim | Própria uso próprio (6.215) + cedente (2.170) |
| Guamaré | Pool uso próprio (7.212) + cedente (1.100) |
| Lem | Própria uso próprio (1.120) + cedente (1.380) |
| São José do Rio Preto | Pool uso próprio (3.398) + cedente (185) |
| Guarulhos | Própria uso próprio (9.662) + cedente (1.175) + cessionária-Democrática (95) |
| Paulínia | Pool uso próprio (11.425) + cessionária-Terceiros (3.895) |
| Cuiabá | Pool uso próprio (1.248) + cessionária-Terceiros (285) |
| Goiânia | Própria uso próprio (3.226) + cessionária-Terceiros (288) |
| Araucária, Itajaí, São Fco do Conde | Democrática + cessionária-Terceiros |
| Biguaçu, Itabuna, Jequié, Rio Grande, Uberaba, Uberlândia | Democrática + cessionária-Democrática |

Nas 18 bases híbridas, o `modelo_operacional` único da aba Capacidade ALE mostra só o papel predominante — para o dashboard, o correto é mostrar a composição por papel (`capacidade_por_modelo.csv`), não um único rótulo.

**Achado confirmado:** Betim é o mesmo caso de Duque de Caxias (própria + cedente, cedendo 2.170 m³ a um terceiro que opera junto, dentro da própria base — só que sem o componente cessionária que Caxias tem em Raízen). E, batendo com a expectativa: **as 5 bases classificadas como `Própria` na aba Capacidade ALE (Betim, Duque de Caxias, Goiânia, Guarulhos, Lem) são todas híbridas — 100%, nenhuma é "própria pura"**. O mesmo vale para as 6 bases `Democrática` (100% híbridas, por natureza — sempre cessionárias em algum congênere) e 4 das 5 `Pool`. Só o modelo `Terceiros` tem a maioria das bases sem hibridismo (24 de 27 puras) — faz sentido, é o modelo em que a ALE já é 100% cessionária por definição, então não há uma "própria" para cruzar com.

| Modelo (Capacidade ALE) | Bases híbridas / total |
|---|---|
| Própria | 5 / 5 |
| Democrática | 6 / 6 |
| Pool | 4 / 5 |
| Terceiros | 3 / 27 |

## Cruzamento com TOP (Take or Pay)

TOP não está em `02 - CAPACIDADES.xlsx` — vem de `arquivos_apoio/Despesas.xlsx` (aba `Despesas`). A chave de junção é `unidade` (Capacidade ALE) normalizada (maiúsculas, sem acento) == `FILIAL` (Despesas.xlsx) normalizada.

**Correção importante:** a primeira versão deste cruzamento usava `codigo_base` == `COD.FILIAL` como chave numérica, achando que era confiável (bateu em 3 testes manuais). Não é — `codigo_base` **não é estável entre abas/arquivos diferentes**: Paulínia é código 12 na Capacidade ALE mas 67 no Despesas.xlsx e no Detalhamento Tancagem; Rondonópolis é 69 vs 61; Cuiabá é 28 vs 73. O nome da unidade, depois de normalizado, bate 100% em todas as fontes — por isso o join foi trocado para usar `unidade` normalizada (`scripts/normalize.py::normalize_municipio`) em vez do código numérico. Esse mesmo cuidado se aplica ao cruzamento com `Detalhamento Tancagem` (seção anterior) — `capacidade_por_modelo.csv` usa o `codigo_base` da própria Detalhamento Tancagem, então `scripts/build_capacidade_dashboard_data.py` também juntou por `unidade`, não por código.

Script: `scripts/build_capacidade_top.py` → `dados_tratados/capacidade_ale_top.csv` (mesmo grão Base x Produto de `capacidade_ale.csv`, com 4 colunas novas):

| Coluna | Descrição |
|---|---|
| `tem_top` | `True` se a base tem ao menos 1 contrato de "Operação Normal" em Despesas.xlsx com Volume Mínimo > 0 (cláusula contratual de garantia, existe independente de ter sido acionada) |
| `congeneres_top` | Congêneres com cláusula TOP identificada nessa base |
| `top_valor_realizado` | Soma histórica (R$) da coluna "Take or Pay" nas linhas realizadas — mesma regra de `dashboard_cessao_aggregate.py::_row_top` (só conta quando há "Valor Total R$" realizado) |
| `meses_com_top_realizado` | Nº de meses distintos em que o TOP foi de fato acionado (valor > 0) |

Resultado: **31 das 43 bases têm TOP**.

**Ponto de atenção:** o flag é por base inteira (via `unidade`), não por produto/tanque. Algumas bases classificadas como `Própria` ou `Pool` na aba Capacidade ALE aparecem com `tem_top=True` (ex.: Betim/Própria com TOP junto à congênere Potencial) — isso é coerente com a aba `Detalhamento Tancagem`, que registra `Tipo De Base` por tanque/linha (não por base inteira): uma base majoritariamente própria pode ter uma fração cedida a terceiros (cessão de espaço) que carrega cláusula TOP, mesmo que o modelo predominante da base seja outro. Se for preciso o TOP no grão tanque/produto, o próximo passo é mapear `Detalhamento Tancagem` e cruzar por lá em vez de por base inteira.

## Dúvidas / pontos em aberto

1. **`capacidade_expedicao_rodo_m3` (coluna P)** só está preenchida numa parte das linhas (bases com expedição rodoviária relevante, ex. Diesel A S500 em Açailândia). Confirmar se célula vazia = "não aplicável" ou = "zero".
2. **Duas linhas de "produto misturado"** (colunas N e S) são idênticas nos exemplos verificados — mantive só a de N (`produto_misturado`); avise se em algum caso elas divergem.
3. A aba **BD Cap Venda ALE** parece ser a base "flat" de onde a "Capacidade ALE" é montada (mesma chave Unidade+Produto), mas tem 305 linhas contra 262 na aba mapeada e não tem a coluna de modelo operacional. Pode haver bases/linhas adicionais fora do relatório final — útil investigar se formos usar essa aba depois.
4. Ainda não mapeei as abas Recebimento/Expedição Rodo - ALE, BD Expedição, BD Descarga e ATA Tancagem — ficam para as próximas rodadas.
