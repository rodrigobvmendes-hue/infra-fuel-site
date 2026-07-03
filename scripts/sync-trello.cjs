#!/usr/bin/env node
/**
 * sync-trello.cjs
 * Sincroniza os cards do board Trello com o trello-status.json.
 *
 * Extrai:
 *   - name, listName, status, due, dueComplete, url
 *   - createdAt  — derivado dos primeiros 8 hex do ID do card (ObjectId timestamp)
 *   - dateLastActivity — retornado diretamente pela API
 *
 * Uso:
 *   TRELLO_KEY=xxx TRELLO_TOKEN=yyy node scripts/sync-trello.cjs
 *
 * Variáveis de ambiente:
 *   TRELLO_KEY    — API key do Trello (obrigatório)
 *   TRELLO_TOKEN  — Token de acesso (obrigatório)
 *   BOARD_ID      — ID do board (padrão: 69f24cd6f0e0329b17b7bcce)
 */

const fs   = require("fs");
const path = require("path");

const KEY      = process.env.TRELLO_KEY;
const TOKEN    = process.env.TRELLO_TOKEN;
const BOARD_ID = process.env.BOARD_ID || "69f24cd6f0e0329b17b7bcce";
const OUT      = path.join(__dirname, "..", "trello-status.json");

if (!KEY || !TOKEN) {
  console.error("❌  Defina TRELLO_KEY e TRELLO_TOKEN como variáveis de ambiente.");
  process.exit(1);
}

// ── Mapa de nome de lista → status interno ────────────────────────────────
const LIST_STATUS = {
  "a fazer":                 "a-fazer",
  "em andamento":            "em-andamento",
  "em andamento/":           "em-andamento",
  "renovações":              "renovacao",
  "renovacoes":              "renovacao",
  "análise de phase-out":    "em-analise",
  "analise de phase-out":    "em-analise",
  "em holding":              "em-holding",
  "concluído":               "concluido",
  "concluido":               "concluido",
};

function toStatus(listName) {
  const key = listName.toLowerCase().trim().normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/\//g, "").trim();
  for (const [k, v] of Object.entries(LIST_STATUS)) {
    const kn = k.normalize("NFD").replace(/\p{Diacritic}/gu, "");
    if (key === kn || key.startsWith(kn)) return v;
  }
  return "em-andamento";
}

// ── Derivar data de criação do ID do card (MongoDB ObjectId) ─────────────
function createdAtFromId(id) {
  // Os primeiros 8 hex chars são o Unix timestamp em segundos
  const ts = parseInt(id.substring(0, 8), 16) * 1000;
  return new Date(ts).toISOString();
}

async function main() {
  const base = "https://api.trello.com/1";
  const auth = `key=${KEY}&token=${TOKEN}`;

  // 1. Busca todas as listas do board
  const listsUrl = `${base}/boards/${BOARD_ID}/lists?fields=id,name&${auth}`;
  const listsRes = await fetch(listsUrl);
  if (!listsRes.ok) throw new Error(`Erro ao buscar listas: ${listsRes.status}`);
  const lists = await listsRes.json();
  const listMap = Object.fromEntries(lists.map(l => [l.id, l.name]));

  // 2. Busca todos os cards do board
  const cardsUrl = `${base}/boards/${BOARD_ID}/cards?fields=id,name,idList,due,dueComplete,shortUrl,dateLastActivity&${auth}`;
  const cardsRes = await fetch(cardsUrl);
  if (!cardsRes.ok) throw new Error(`Erro ao buscar cards: ${cardsRes.status}`);
  const cards = await cardsRes.json();

  // 3. Monta o JSON final
  const result = {
    updatedAt: new Date().toISOString(),
    boardId:   BOARD_ID,
    cards: cards.map(c => {
      const listName = listMap[c.idList] || "Desconhecido";
      return {
        name:             c.name,
        listName:         listName,
        status:           toStatus(listName),
        due:              c.due   ? c.due.slice(0, 10) : null,
        dueComplete:      c.dueComplete,
        url:              c.shortUrl,
        createdAt:        createdAtFromId(c.id),
        dateLastActivity: c.dateLastActivity,
      };
    }),
  };

  fs.writeFileSync(OUT, JSON.stringify(result, null, 2), "utf8");
  console.log(`✅  ${result.cards.length} cards salvos em trello-status.json`);
  console.log(`   Atualizado em: ${result.updatedAt}`);
}

main().catch(err => { console.error("❌ ", err.message); process.exit(1); });
