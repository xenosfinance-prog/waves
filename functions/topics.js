// /topics — indice dei temi del blog (stesso codice di functions/topics/[[path]].js)
import { onRequestGet as handler } from './topics/[[path]].js';

export async function onRequestGet(context) {
  return handler(context);
}
