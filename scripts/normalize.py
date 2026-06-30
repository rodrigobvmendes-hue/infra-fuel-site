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
