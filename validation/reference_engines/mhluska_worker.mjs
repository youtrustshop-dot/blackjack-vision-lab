// Independent public Game.step client; no upstream source modification.
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const checkout = path.resolve(process.argv[2]);
const request = JSON.parse(fs.readFileSync(0, 'utf8'));
const api = await import(
  pathToFileURL(path.join(checkout, 'dist', 'main.js')).href
);
const { Game, GameStep, GameMode } = api;
// Move / BlackjackPayout are not exported by the upstream public entrypoint.
// These enum positions are checked against pinned src/types.ts by the runner.
const Stand = 5, NoInsurance = 3, ThreeToTwo = 0;
const rounds = request.rounds;
if (!Number.isInteger(rounds) || rounds < 1 || rounds > 10000000) {
  throw new Error('Invalid rounds');
}
const settings = {
  disableEvents: true, debug: false, checkDeviations: false,
  autoDeclineInsurance: false, mode: GameMode.Default,
  playerBankroll: 1e12, playerTablePosition: 1,
  playerStrategyOverride: {}, playerCount: 1,
  deckCount: request.decks, hitSoft17: request.hit_soft17,
  allowDoubleAfterSplit: true, allowLateSurrender: false,
  allowResplitAces: false, maxHandsAllowed: 4,
  blackjackPayout: ThreeToTwo, minimumBet: 100, maximumBet: 100,
  penetration: 1 / (request.decks * 52)
};
const game = new Game(settings);
game.betAmount = 100;
game.spotCount = 1;
const effectiveSettings = JSON.parse(JSON.stringify(game.settings));
let sum = 0, won = 0, lost = 0, pushed = 0;
const initialBalance = game.player.balance;
const start = performance.now();
for (let round = 0; round < rounds; ++round) {
  if (game.state.step !== GameStep.Start || game.shoe.cardCount !== request.decks * 52) {
    throw new Error('Round is not starting with a complete fresh shoe');
  }
  const balance = game.player.balance;
  let steps = 0;
  while (game.state.step !== GameStep.WaitingForNewGameInput) {
    if (++steps > 40) throw new Error('Unexpected step loop');
    const input = game.state.step === GameStep.WaitingForInsuranceInput ? NoInsurance :
                  game.state.step === GameStep.WaitingForPlayInput ? Stand : undefined;
    game.step(input);
  }
  const profit = (game.player.balance - balance) / 100;
  if (![-1, 0, 1, 1.5].includes(profit) || game.player.handWinner.size !== 1) {
    throw new Error('Unexpected settlement for fixed stand policy');
  }
  sum += profit;
  if (profit > 0) ++won; else if (profit < 0) ++lost; else ++pushed;
  game.step(Stand); // Public new-game acknowledgement; cleans and reshuffles.
}
if (Math.abs(sum - (game.player.balance - initialBalance) / 100) > 1e-10) {
  throw new Error('Bankroll and round profits disagree');
}
console.log(JSON.stringify({status: 'executed', rounds, ev: sum / rounds,
  total_profit: sum, hands_won: won, hands_lost: lost, hands_pushed: pushed,
  policy: 'public Game.step; stand; decline insurance; fixed bet 100 cents',
  effective_settings: effectiveSettings, latency_ms: performance.now() - start,
  rng: 'Unmodified upstream Math.random; fresh uniformly shuffled six-deck shoe each round'}));
