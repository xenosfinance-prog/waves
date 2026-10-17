// /setups (pagina indice). index.js nella cartella non veniva instradato da Pages:
// route esplicita a livello superiore, stesso handler del catch-all.
import { onRequestGet as handler } from './setups/[[path]].js';

export async function onRequestGet(context) {
  return handler(context);
}
