#!/usr/bin/env node
/**
 * Varredura semanal de infraestrutura de combustíveis claros (Brasil).
 *
 * O QUE FAZ:
 *  1. Lê o data.js do repositório e extrai a lista de projetos já conhecidos.
 *  2. Chama a Claude API com a ferramenta web_search, pedindo NOVOS projetos
 *     e ATUALIZAÇÕES de projetos existentes, focado em derivados claros.
 *  3. Salva o resultado em dados_brutos/varredura-AAAA-MM-DD.json (para revisão).
 *
 * NÃO faz merge automático no data.js. A saída é só para o Rodrigo aprovar.
 *
 * Requisitos: Node 18+ (fetch nativo). Variável de ambiente CLAUDE_API_KEY.
 */

const fs = require("fs");
const path = require("path");
const vm = require("vm");

// ─── Config ──────────────────────────────────────────────────────────────
const API_KEY = process.env.CLAUDE_API_KEY;
const MODEL = "claude-sonnet-4-6";
const MAX_SEARCHES = 12;          // teto de buscas por execução (controla custo)
const DATA_FILE = process.env.DATA_FILE || "data.js";
const OUTPUT_DIR = process.env.OUTPUT_DIR || "dados_brutos";

// Fontes prioritárias (o modelo é instruído a privilegiá-las e sempre citar URL).
const FONTES_PRIORITARIAS = [
  "ANP — Agência Nacional do Petróleo (gov.br/anp, dados abertos)",
  "ANTT — ferrovias e projetos terrestres (gov.br/antt)",
  "ANTAQ — terminais e portos (gov.br/antaq)",
  "Ministério de Portos e Aeroportos (gov.br/portos-e-aeroportos)",
  "Ministério de Minas e Energia (gov.br/mme)",
  "Petrobras / Transpetro (RI e agência de notícias)",
  "Raízen, Vibra, Ultracargo, Ipiranga, Inpasa, Acelen (RI)",
  "Complexo do Pecém, Porto de Santos, demais autoridades portuárias",
];

const FOCO_COMBUSTIVEIS =
  "Gasolina, diesel (S-10/S-500), etanol anidro, etanol hidratado, biodiesel/B100, " +
  "diesel marítimo / marine / bunker, QAV/SAF, GLP, e AMPLIAÇÕES de capacidade de refino. " +
  "Tipos de ativo de interesse: refinarias, terminais, bases de distribuição, oleodutos/polidutos, " +
  "ferrovias que movimentam combustíveis e biocombustíveis.";

// ─── 1. Carrega projetos conhecidos do data.js ───────────────────────────
function carregarConhecidos(arquivo) {
  const code = fs.readFileSync(arquivo, "utf8");
  const sandbox = {};
  vm.createContext(sandbox);
  // data.js define `const PROJECTS = [...]` no escopo do arquivo.
  // Reexpomos via globalThis para conseguir capturar o array.
  vm.runInContext(code + "\nglobalThis.__PROJECTS__ = PROJECTS;", sandbox);
  const projetos = sandbox.__PROJECTS__;
  if (!Array.isArray(projetos)) {
    throw new Error("Não encontrei o array PROJECTS dentro de " + arquivo);
  }
  return projetos;
}

// Lista compacta para o prompt (não precisa mandar descrições inteiras).
function resumirConhecidos(projetos) {
  return projetos
    .map((p) => {
      const empresas = Array.isArray(p.companies) ? p.companies.join(", ") : "";
      return `- [${p.type}] ${p.name} | ${p.state} | ${p.status} | ${empresas}`;
    })
    .join("\n");
}

// ─── 2. Monta e dispara a chamada à Claude API ───────────────────────────
function montarPrompt(listaConhecidos) {
  return `Você é um analista de inteligência de infraestrutura do setor de combustíveis no Brasil.

TAREFA: usando busca na web, identifique (A) NOVOS projetos e (B) ATUALIZAÇÕES de projetos já existentes na minha base, relativos a infraestrutura de combustíveis claros e derivados no Brasil.

FOCO DE PRODUTO/ATIVO:
${FOCO_COMBUSTIVEIS}

FONTES PRIORITÁRIAS (privilegie estas; busque também notícias recentes que apontem para elas):
${FONTES_PRIORITARIAS.map((f) => "- " + f).join("\n")}

JANELA TEMPORAL: priorize anúncios, licitações, audiências públicas, contratos e mudanças de status dos últimos ~3 meses.

BASE ATUAL (projetos JÁ conhecidos — use para decidir se algo é NOVO ou ATUALIZAÇÃO):
${listaConhecidos}

REGRAS CRÍTICAS:
1. Cada item DEVE ter uma URL de fonte verificável (campo "fonte_url"). Sem URL = não inclua.
2. NÃO invente projetos, números ou status. Se não tiver certeza, omita.
3. "novo" = não consta na base atual. "atualizacao" = já consta, mas houve mudança de status, capacidade, investimento, prazo ou empresa.
4. Para atualizações, informe o que mudou no campo "mudanca".
5. Ignore qualquer item que não seja de combustíveis claros/derivados ou ampliação de refino.

FORMATO DE SAÍDA: responda APENAS com um objeto JSON válido, sem markdown, sem texto antes ou depois, exatamente neste schema:

{
  "data_varredura": "AAAA-MM-DD",
  "resumo": "1-2 frases sobre o que foi encontrado",
  "novos": [
    {
      "name": "",
      "type": "Refinaria|Terminal|Oleoduto|Base|Etanol|Ferrovia",
      "state": "UF",
      "status": "Planejado|Em Construção|Em Operação",
      "companies": [""],
      "fuel": "",
      "capacity": "",
      "investment": "",
      "description": "",
      "fonte_url": "",
      "confianca": "alta|media|baixa"
    }
  ],
  "atualizacoes": [
    {
      "name_na_base": "nome aproximado como aparece na base atual",
      "mudanca": "o que mudou",
      "novo_status_ou_dado": "",
      "fonte_url": "",
      "confianca": "alta|media|baixa"
    }
  ]
}

Se não encontrar nada novo ou atualizado, retorne "novos": [] e "atualizacoes": [].`;
}

async function chamarClaude(prompt) {
  const resp = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 8000,
      messages: [{ role: "user", content: prompt }],
      tools: [
        {
          type: "web_search_20250305",
          name: "web_search",
          max_uses: MAX_SEARCHES,
        },
      ],
    }),
  });

  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`API HTTP ${resp.status}: ${txt}`);
  }
  return resp.json();
}

// Concatena todos os blocos de texto e isola o JSON.
function extrairJSON(data) {
  const texto = (data.content || [])
    .filter((b) => b.type === "text")
    .map((b) => b.text)
    .join("\n")
    .trim();

  let limpo = texto.replace(/```json/gi, "").replace(/```/g, "").trim();

  // fallback: pega do primeiro { ao último }
  const ini = limpo.indexOf("{");
  const fim = limpo.lastIndexOf("}");
  if (ini !== -1 && fim !== -1) limpo = limpo.slice(ini, fim + 1);

  try {
    return { ok: true, json: JSON.parse(limpo), raw: texto };
  } catch (e) {
    return { ok: false, erro: e.message, raw: texto };
  }
}

// ─── 3. Execução ─────────────────────────────────────────────────────────
(async () => {
  if (!API_KEY) {
    console.error("ERRO: variável CLAUDE_API_KEY não definida.");
    process.exit(1);
  }

  const hoje = new Date().toISOString().slice(0, 10);

  console.log(`[${hoje}] Lendo ${DATA_FILE}...`);
  const conhecidos = carregarConhecidos(DATA_FILE);
  console.log(`Projetos conhecidos na base: ${conhecidos.length}`);

  const prompt = montarPrompt(resumirConhecidos(conhecidos));

  console.log(`Chamando Claude API (web_search, max ${MAX_SEARCHES} buscas)...`);
  const data = await chamarClaude(prompt);

  const buscas =
    data.usage && data.usage.server_tool_use
      ? data.usage.server_tool_use.web_search_requests
      : "n/d";
  console.log(`Buscas executadas: ${buscas}`);

  const resultado = extrairJSON(data);

  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  const outPath = path.join(OUTPUT_DIR, `varredura-${hoje}.json`);

  if (!resultado.ok) {
    // não perde o trabalho: salva o texto bruto para inspeção manual
    const fallback = {
      data_varredura: hoje,
      erro_parse: resultado.erro,
      resposta_bruta: resultado.raw,
    };
    fs.writeFileSync(outPath, JSON.stringify(fallback, null, 2), "utf8");
    console.error("AVISO: não consegui parsear JSON. Salvei resposta bruta em " + outPath);
    process.exit(0);
  }

  const saida = {
    ...resultado.json,
    _meta: {
      gerado_em: new Date().toISOString(),
      modelo: MODEL,
      buscas_web: buscas,
      total_conhecidos: conhecidos.length,
    },
  };

  fs.writeFileSync(outPath, JSON.stringify(saida, null, 2), "utf8");

  const nNovos = (saida.novos || []).length;
  const nAtu = (saida.atualizacoes || []).length;
  console.log(`Pronto: ${nNovos} novos, ${nAtu} atualizações -> ${outPath}`);
})().catch((e) => {
  console.error("FALHA:", e.message);
  process.exit(1);
});
