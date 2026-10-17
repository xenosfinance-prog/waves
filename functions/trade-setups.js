// /trade-setups (pagina indice dei setup; le singole pagine restano su /setups/<slug>).
// route esplicita a livello superiore, stesso handler del catch-all.
import { onRequestGet as handler } from './setups/[[path]].js';

export async function onRequestGet(context) {
  return handler(context);
}
