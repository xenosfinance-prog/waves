// /setups (pagina indice). Il parser delle route di Pages riconosce solo gli handler
// dichiarati nel file stesso, non i re-export: per questo il wrapper esplicito.
import { onRequestGet as handler } from './[[path]].js';

export async function onRequestGet(context) {
  return handler(context);
}
