"""Regras de normalização e de geração de chaves/identificadores estáveis."""

import hashlib
import re
import unicodedata

# Formas pontuadas (S/A, S.A., LTDA.) precisam ser removidas antes da
# pontuação genérica, ou a barra/ponto vira espaço e quebra o sufixo em
# tokens separados (ex.: "S/A" -> "S A").
_PUNCTUATED_SUFFIX_PATTERN = re.compile(r"\bS[./]A\.?\b|\bLTDA\.\b")
_BARE_SUFFIX_PATTERN = re.compile(r"\b(?:SA|LTDA|EIRELI)\b")
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)
_MULTISPACE_PATTERN = re.compile(r"\s+")


def _upper_no_accents(text: str) -> str:
    text = text.upper()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def normalize_empresa(razao_social: str) -> str:
    """Converte uma razão social na chave Empresa_Normalizada.

    Passos: maiúsculas -> remove acentos -> remove sufixos societários
    pontuados (S/A, S.A., LTDA.) -> remove pontuação -> remove sufixos
    societários sem pontuação (SA, LTDA, EIRELI) -> colapsa espaços -> strip.
    """
    if not razao_social:
        return ""

    text = _upper_no_accents(razao_social)
    text = _PUNCTUATED_SUFFIX_PATTERN.sub(" ", text)
    text = _PUNCTUATION_PATTERN.sub(" ", text)
    text = _BARE_SUFFIX_PATTERN.sub(" ", text)
    text = _MULTISPACE_PATTERN.sub(" ", text).strip()
    return text


def normalize_municipio(municipio: str) -> str:
    """Converte um nome de município na chave Municipio_Normalizado.

    Passos: maiúsculas -> remove acentos -> remove pontuação -> colapsa
    espaços duplicados -> strip.
    """
    if not municipio:
        return ""

    text = _upper_no_accents(municipio)
    text = _PUNCTUATION_PATTERN.sub(" ", text)
    text = _MULTISPACE_PATTERN.sub(" ", text).strip()
    return text


_LEGAL_SUFFIX_TAIL_PATTERN = re.compile(
    r"\s*[-–.]?\s*(S\.?/?A\.?|LTDA\.?|EIRELI|M\.?E\.?|EPP)\.?\s*$", re.IGNORECASE
)
_ACTIVITY_CUT_PATTERN = re.compile(
    r"\b(DISTRIBUIDORA(S)?|COM[EÉ]RCIO|TRANSPORTADORA|TRANSPORTE(S)?|COMERCIAL)\b",
    re.IGNORECASE,
)
_TRAILING_CONNECTOR_PATTERN = re.compile(
    r"\s+(E|DE|DO|DA|DOS|DAS)$", re.IGNORECASE
)


def nome_reduzido(razao_social: str) -> str:
    """Melhor esforço: deriva um nome curto a partir da razão social.

    Corta a razão social no primeiro descritor genérico de atividade
    (DISTRIBUIDORA, COMÉRCIO, TRANSPORTADORA...) que não seja a primeira
    palavra, e remove sufixos societários residuais (S/A, LTDA, EIRELI).
    Não é 100% preciso para todos os casos (ex.: nomes que começam com o
    próprio descritor) -- ajustes finos devem ser feitos manualmente no
    CSV de alias.
    """
    text = (razao_social or "").strip()
    if not text:
        return ""

    for m in _ACTIVITY_CUT_PATTERN.finditer(text):
        if m.start() > 0:
            text = text[: m.start()].strip()
            break

    text = _LEGAL_SUFFIX_TAIL_PATTERN.sub("", text).strip()
    text = _TRAILING_CONNECTOR_PATTERN.sub("", text).strip()
    text = _MULTISPACE_PATTERN.sub(" ", text).strip(" -–,")
    return text or razao_social.strip()


# ---------------------------------------------------------------------------
# Consolidação de grupo empresarial (marcas/subsidiárias que são, na prática,
# a mesma controladora -- ex.: aquisições). Isto é conhecimento de negócio
# que não dá pra inferir da razão social, por isso é uma lista curada
# manualmente. Fonte única para todos os dashboards do pipeline: qualquer
# tela que agrupe capacidade/instalações "por empresa" deve usar
# grupo_empresarial()/nome_grupo() em vez de normalize_empresa()/
# nome_reduzido() direto, para herdar essas consolidações automaticamente.
#
# Histórico registrado:
# - Petróleo Sabbá -> Raízen (aquisição, 2023)
# - Raízen Mime Combustíveis -> Raízen (mesma controladora)
# ---------------------------------------------------------------------------
_GRUPO_EMPRESARIAL_ALIASES = {
    "PETROLEO SABBA": "RAIZEN",
    "RAIZEN MIME COMBUSTIVEIS": "RAIZEN",
}
_GRUPO_NOME_EXIBICAO = {
    "RAIZEN": "Raízen",
}


def grupo_empresarial(razao_social: str) -> str:
    """Chave de agrupamento por GRUPO empresarial (pode juntar CNPJs/razões
    sociais distintas sob a mesma controladora). Usar apenas em telas de
    exibição/ranking -- não em reconciliações ANP x bases autorizadas, onde
    a razão social original de cada CNPJ importa para a validação."""
    key = normalize_empresa(razao_social)
    return _GRUPO_EMPRESARIAL_ALIASES.get(key, key)


def nome_grupo(razao_social: str) -> str:
    """Nome de exibição do grupo empresarial (ex.: 'Raízen' para Sabbá e
    Raízen Mime). Cai para nome_reduzido() quando não há consolidação
    conhecida para essa empresa."""
    grupo_key = grupo_empresarial(razao_social)
    return _GRUPO_NOME_EXIBICAO.get(grupo_key, nome_reduzido(razao_social))


def build_localizacao_key(uf: str, municipio_normalizado: str) -> str:
    """Combinação estável de UF + Município normalizado."""
    uf_norm = (uf or "").strip().upper()
    return f"{uf_norm}|{municipio_normalizado or ''}"


def stable_id(prefix: str, *parts: str) -> str:
    """Identificador técnico estável a partir do conteúdo dos campos informados.

    Usa um hash determinístico (SHA-1) do conteúdo, não da posição/linha,
    para que o mesmo conjunto de valores sempre gere o mesmo identificador.
    """
    raw = "|".join((p or "").strip() for p in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"
