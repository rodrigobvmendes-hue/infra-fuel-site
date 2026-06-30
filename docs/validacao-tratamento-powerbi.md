# Validação do tratamento de dados — Power BI

Relatório gerado automaticamente pelo pipeline (`extract_raw.py` -> `build_dim_empresa.py` -> `build_dim_localizacao.py`).

## Registros antes e depois

- ANP — registros: 1554 (antes) / 1554 (depois)
- Bases autorizadas — registros: 472 (antes) / 472 (depois)

## Totais agregados

- Soma da tancagem ANP (m³): 46161750.00 (antes) / 46161750.00 (depois)
- Soma da capacidade total (bases autorizadas): 8328734.61 (antes) / 8328734.61 (depois)
- Confirmação: nenhuma capacidade ou tancagem foi consolidada, somada ou duplicada entre registros — os totais antes e depois são idênticos porque o tratamento apenas adiciona colunas derivadas, sem agregar ou remover linhas.

## Qualidade dos dados

- CNPJs duplicados (registros com `Flag_CNPJ_Duplicado = S`): 2
- Registros incompletos (campos críticos, desconsiderando `Complemento`): 6

## Relacionamento entre fontes — Empresas

- Total de empresas distintas (`dim_empresa.csv`): 1101
- Empresas presentes nas duas fontes (ANP e bases autorizadas): 109
- Empresas presentes somente na ANP: 920
- Empresas presentes somente nas bases autorizadas: 72

## Relacionamento entre fontes — Localizações

- Total de localizações distintas (`dim_localizacao.csv`): 773
- Localizações presentes nas duas fontes: 133
- Localizações presentes somente na ANP: 639
- Localizações presentes somente nas bases autorizadas: 1

## Unicidade dos identificadores técnicos

- `Id_Instalacao_ANP` — valores duplicados: 0 (de 1554 registros)
- `Id_Base_Autorizada` — valores duplicados: 0 (de 472 registros)
- `Empresa_Key` (`dim_empresa.csv`) — valores duplicados: 0 (de 1101 registros)
- `Localizacao_Key` (`dim_localizacao.csv`) — valores duplicados: 0 (de 773 registros)
