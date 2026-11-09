# Learning Notes (Roman Urdu)

Har phase ke baad yahan simple alfaaz mein likha jayega: kya banaya, kyun, kaise kaam karta hai,
aur Claude Code ka kaun sa mechanism mirror karta hai.

---

## Phase 0 — Research aur Plan

### Kya kiya?
- Professor ki instructions, dono architecture files aur teen reference repos parhe.
- DeepSeek ki official docs se API ki asal details check ki.
- Project folder banaya, input files copy ki, aur `.gitignore` banaya taake API key kabhi GitHub par na jaye.

### Do programs ka farq (sab se zaroori baat)
- **Program A = Code Agent**: ye hum banayenge. Ek chhota sa "Claude Code" jaisa program jo DeepSeek AI se baat karta hai.
- **Program B = Space Fractions game**: ye hum **nahi** likhenge. Ye agent khud DeepSeek ki madad se likhega.
  Hum sirf agent ko instructions (system prompt) aur tools denge.

### Agent kaise kaam karta hai (simple misaal)
Socho ek naya intern hai (AI model). Hum usay:
1. **Kaam ki detail** dete hain (spec.json — architecture docs ko saaf JSON mein badal kar).
2. **Auzaar (tools)** dete hain: file parhna, file likhna, file mein chhoti tabdeeli karna, test chalana.
3. Ek **loop** chalate hain: intern bolta hai "ye file likho" → hum likh kar result batate hain → wo agla qadam batata hai...
   jab tak wo "finish" na bole.
Yahi Claude Code ka **agent loop** hai.

### Research mein kya naya mila?
- OpenRouter par DeepSeek V4 ka **free** model ab maujood nahi. Demo run ke liye baad mein faisla karna hoga.
- DeepSeek mein "thinking mode" default ON hota hai. Hum isay OFF rakhenge (sasta). ON karein to `reasoning_content`
  wapas bhejna zaroori hai warna error aata hai.
- Flash model ka naya naam `deepseek-flash` hai.

### Input docs ki ghaltiyan (agent ko pakarni hain)
- Docs **web/microservices** keh rahi hain, professor **desktop** app chahte hain → agent adapt karega
  (PostgreSQL → SQLite, REST → Python functions, Kubernetes → zaroorat nahi).
- Testing table khaali hai, file naam mismatch (`question_ddl.sql` vs `game_ddl.sql`), UML mein galat syntax (`->>`).

### Interview mein kaise samjhayein
"Main ne Claude Code ke andar ke mechanisms parhe — agent loop, tools, plan mode, context compaction,
permissions — aur unka chhota Python version banaya jo DeepSeek ke saath architecture docs se poora desktop game generate karta hai."

---

## Phase 1 — Config, LLM providers, aur Parsers

### 1) LLM Provider (AI se baat karne wala hissa)
- `LLMProvider` ek **interface** hai, yani ek "plug ka shape". Agent sirf is shape ko jaanta hai.
- Is shape mein do plug lagte hain:
  - **DeepSeekProvider** — asal API (`deepseek-v4-pro`), paise lagte hain. Thinking mode hum OFF bhejte hain (sasta).
    Error aaye (429 rate limit, 500/503 server) to thora ruk kar dobara try karta hai (**retry with backoff**).
    401 (ghalat key) ya 402 (balance khatam) par saaf message deta hai.
  - **MockProvider** — nakli AI. Hum pehle se likh dete hain ke "pehle ye tool call karo, phir ye". Koi paisa nahi,
    har dafa bilkul same result → tests reliable. Ye claw-code ke **mock parity harness** jaisa hai.
- `pricing.py` — tokens se kharcha nikalta hai (cache hit sasta, cache miss mehnga, output sab se mehnga; peak hours mein 2×).

### 2) Config
- API key GUI se `%APPDATA%\SpaceFractionsAgent\config.json` mein save hogi — repo mein kabhi nahi.
- Dev mode mein `.env` se bhi parh leta hai. `mask_key()` key ke sirf aakhri 4 harf dikhata hai.

### 3) Parsers (markdown → JSON) — bina AI ke
- `doc_parser.py`: architecture doc ke sections A–L, tables, code blocks (OpenAPI, SQL, proto, k8s, CSV), requirements,
  components, assumptions nikalta hai.
- `uml_parser.py`: 13 PlantUML diagrams parhta hai — actors, use cases, classes (attributes/methods), states, sequence messages.
  Ghalat syntax (`->>`, object diagram mein `participant`) par **crash nahi karta**, warning likh deta hai.
- `spec.py`: dono ko jor kar `spec.json` banata hai + `domain_model` (chhota khulasa jo AI ko diya jayega).
  Is mein koi timestamp nahi — har dafa bilkul same, taake DeepSeek ka **prompt cache** hit ho aur kharcha kam ho.
- **Issues khud pakre** (7 types): khaali testing table, file naam mismatch, kam requirements, copy-paste justifications,
  duplicate blocks, web vs desktop conflict, UML syntax ghaltiyan.

### 4) Security
- Pre-commit hook: har commit se pehle `sk-...` jaisi key dhoondta hai; mile to commit **rok** deta hai.

### Interview line
"Main ne input ko pehle deterministic parser se structured JSON mein badla — ye sasta, testable aur reproducible hai.
AI sirf wahan use hota hai jahan zaroori hai: design decisions aur code likhna."

---

## Phase 2 — Tools, Sandbox, Agent Loop (agent ka dil)

### 1) Agent loop — do layers (Claude Code jaisa)
- **Bahar wali layer** (`Agent.run`): poora session sambhalti hai — messages, tokens, kharcha, `state.json`.
  Phases chalati hai: **plan → implement → verify ⇄ fix → report**.
- **Andar wali layer** (`_run_phase`): ek chakkar (loop): AI ko messages + tools bhejo → AI tool calls lautaye →
  hum tools chalayein → result `role:"tool"` message mein wapas → dobara... jab tak `submit_plan`/`finish` na aaye.
- Agar AI tool call na kare → 2 dafa yaad dilate hain (nudge); jawab beech mein kat jaye (`length`) → "continue" bolte hain.

### 2) Plan mode
- Plan phase mein AI sirf **parh** sakta hai (list_dir, read_file...) aur `update_todos` + `submit_plan`.
  Likhne ki koshish kare to "Permission denied: not available in plan mode" milta hai.
- `submit_plan` mein AI `DESIGN_DECISIONS.md` ka content + file tree + notes deta hai; **harness khud** file likhta hai
  (bilkul Claude Code ke ExitPlanMode jaisa).

### 3) Tools aur Sandbox (hifazat)
- Har path output folder ke andar hi hona chahiye — `../` ya `C:\...` block. `agent_run/` folder AI ke liye read-only.
- `.bat/.exe/.ps1` jaisi files likhna mana. Koi shell nahi.
- `edit_file`: exact text dhoond kar badalta hai; text **ek hi dafa** mile warna error ("Found 2 matches...").
  Pehle file **poori parhna** zaroori; parhne ke baad kisi aur ne file badli ho to dobara parhna padta hai.
- `write_files`: ek hi call mein kai files — **requests bachti hain** (paisa bachta hai).
- Read-only tools ek saath (parallel) chalte hain, likhne wale ek-ek kar ke.
- Tool ka error crash nahi karta — AI ko "Error: ..." result milta hai taake wo khud theek kare.

### 4) Self-verification
- AI `finish` bole to harness khud check karta hai: zaroori files hain? sab `.py` compile hoti hain? pytest pass?
- Fail ho to report AI ko "FIX phase" mein milti hai — max `fix_rounds` dafa.
- Tests **bundled interpreter** se chalte hain (`app.main --run-pytest`) — exe mein bhi Python ki zaroorat nahi.

### 5) Context management (3 levels)
1. Bara tool output (8000+ chars) → poora file mein save, AI ko sirf shuru + aakhir + file ka path.
2. Microcompact → purane tool results ki jagah chhota placeholder.
3. Auto-compact → beech ki baatcheet ka khulasa (summary) bana kar replace; system prompt + spec kabhi nahi chhede
   (taake **cache** hit hota rahe), aur current phase ki instructions dobara likh di jati hain.

### 6) Budget aur hifazati limits
- Max LLM requests (40), max cost ($1), max tokens, max steps, Stop button → run aaram se rukta hai, sab save.
- **Resume**: `state.json` se wahin se dobara shuru.
- **Replay**: recorded transcript ke AI jawab dobara chala kar poora project dobara banata hai — **zero kharcha**,
  report par saaf likha hota hai "REPLAY of a recorded run".

### 7) Testing (mock parity harness)
- 15 end-to-end scenarios MockProvider ke saath: happy path, fix round, plan mode write denied, budget stop, cost cap,
  resume, nudges, length continue, auto-compaction, replay, user stop, bara output, ghalat JSON. Sab bina paise ke.

### Interview line
"Mera agent Claude Code ki tarah two-layer loop chalata hai, plan mode mein sirf read-only tools deta hai, code ko
search-and-replace se edit karta hai, khud tests chala kar apni ghaltiyan theek karta hai, aur har request ka
kharcha track karta hai. Sab kuch MockProvider se deterministic tested hai."

---

## Phase 3 — GUI (desktop window)

### Kya bana
- **customtkinter** window (Windows desktop look). Chalane ka tareeqa (dev): `python -m sfagent.main`.
- **Bayen taraf (settings):** DeepSeek API key (•••• chhupi hui, 👁 se dikh sakti hai), "Remember key", Test connection,
  Thinking mode, Mock mode; dono `.md` files ke pickers (samples/ se khud bhar jaate hain); output folder; limits
  (steps, requests, cost $, fix rounds); "Ask before every file write".
- **Neeche fixed buttons:** Generate, Stop, Resume, Replay, Open output folder, **▶ Run generated game**.
- **Dayen taraf:** phases ki patti (Plan → Implement → Verify → Fix → Report; chal raha = orange, ho gaya = green),
  tabs: Log (har tool call: `→ write_files main.py, ...`), Todos (○ ◐ ●), Spec preview, Report; neeche kharcha line.

### Window freeze kyun nahi hoti? (zaroori concept)
- Agent ek **alag thread** (worker) mein chalta hai. Wo har cheez ek **queue** mein daalta hai (log, phase, todos...).
- Window har 100ms baad queue check karti hai aur screen update karti hai. Is liye AI ka jawab aane tak bhi window chalti rehti hai.
- "Ask before write" mein worker ruk kar intezar karta hai; window Yes/No poochti hai aur jawab wapas worker ko deti hai.

### Hifazati baatein
- Asal DeepSeek run se pehle **confirmation**: price + is run ki hard limits ($ aur requests).
- Naya run sirf **khaali folder** mein (do runs mix na hon; hum kuch delete nahi karte).
- Mock mode aur Replay par upar saaf banner: "MOCK MODE — no API calls" / "REPLAY of recorded run".
- Mock demo project ke README aur window par likha hai: "NOT generated by an LLM" — imaandari.

### Interview line
"GUI non-blocking hai: agent worker thread mein chalta hai aur events queue ke zariye UI tak aate hain. User har waqt
Stop kar sakta hai, state save hoti hai, aur Resume se wahin se dobara chal sakta hai."

---

## Phase 4 — `.exe` banana (Python ke baghair chalne wali app)

### PyInstaller kya karta hai?
- Hamara Python code + Python interpreter (python312.dll) + saari libraries (customtkinter, openai, pytest...) ko
  **ek hi file** `SpaceFractionsAgent.exe` (26 MB) mein pack kar deta hai. Double-click → khul jati hai.
- `--onefile --windowed`: ek file, aur kala console window nahi aata.

### Asal mushkil: generated game kaise chalega jab PC par Python hi nahi?
- Hal: exe ke andar ka Python hi istemal karte hain. Exe ke **chhupe hue commands**:
  - `SpaceFractionsAgent.exe --run-pytest tests` → generated tests chalata hai
  - `SpaceFractionsAgent.exe --run-script main.py` → generated game chalata hai ("▶ Run generated game" yahi karta hai)
  - `--doctor` (sehat check), `--self-test` (poora mock pipeline exe ke andar)
- Lekin exe mein sirf wo modules hote hain jo hamare code ne import kiye. Isliye `app/bundled.py` mein ek **list** hai
  (tkinter, sqlite3, fractions, random...) jo exe mein zabardasti daali jati hai **aur** AI ko system prompt mein bataya
  jata hai ke sirf yehi modules use kare. Dono jagah ek hi list → kabhi mismatch nahi.
- Windowed exe ka console nahi hota, to output ek file mein likhwate hain (`SFA_OUTPUT_FILE`) aur wahan se parhte hain.

### Kaise prove kiya ke Python ke baghair chalti hai?
- `scripts/verify_exe.py`: exe ko aisa environment deta hai jismein PATH par sirf Windows folders hain (koi Python nahi)
  aur 6 cheezein check karta hai: version, doctor, self-test (agent → child exe → pytest "2 passed"), script run
  (`frozen True`), GUI window khulna, game window khulna. **6/6 PASS** — mere PC par bhi aur GitHub ke saaf Windows
  runner par bhi.

### GitHub Actions (CI)
- Har push par GitHub ki Windows machine: lint → 81 tests → exe build → verify_exe → exe ko "artifact" bana ke upload.
- `v1.0.0` jaisa tag lagayen to **Release** khud ban jati hai aur exe attach ho jata hai (professor wahan se download karenge).

### Ek ahem fix
- AI ek jawab mein max 8K tokens likh sakta tha — poore game ka code isse bara hai, jawab beech mein kat jata.
  Limit 32K ki aur AI ko kaha 4–6 files per call likho.

### Interview line
"Exe ke andar ka interpreter hi generated code chalata hai via hidden sub-commands, aur bundled stdlib list system
prompt mein bhi di jati hai. CI har commit par exe build kar ke bina-Python environment mein verify karta hai."

---

## UI/UX round 2 — kya badla (aasan alfaaz)

1. **Kaam khatam hone ka saaf signal:** run kamyab ho to hara popup "Project generated successfully! Tests: PASSED"
   aur 3 buttons (Run generated app / Open folder / Close). Fail ya stop ho to laal popup + wajah.
2. **"Run generated app" button sirf tab chalta hai jab folder mein kamyab run ho** — warna grey. Kamyab hone par
   hara, bold, aur halka sa "pulse" (chamakta) karta hai taake video mein nazar aaye.
3. **Bhara hua output folder:** ab sirf error nahi — 4 options: naya subfolder (behtar), purana run overwrite
   (sirf agent ki banayi files delete, aap ki apni files mehfooz), resume, cancel.
4. **API key button:** "Show" dabane par "Hide" ho jata hai (aur ulta).
5. **Game ki khoobsurti — AI ko qaide diye, game khud nahi likha:**
   - System prompt mein **generic UI rules**: badi window (kam az kam 1100×750, maximized, F11/Esc), bare fonts,
     hover wale bare buttons, Enter se submit, jawab ke baad input khud saaf, hara/laal feedback.
   - Space Fractions profile mein **bachon ke liye** rules: space theme, sitare/planets, "Question 3 of 10",
     Pause button, "Congratulations, <naam>!" + 1–3 sitare + confetti.
   - **Verify ab UI bhi check karta hai:** AI ko `tests/test_ui_smoke.py` likhna lazmi — jo window bana kar size
     aur widgets check kare. Chhoti/kharab UI hogi to test fail → AI khud theek karega.
6. **Mock demo** (jis par saaf "MOCK DEMO — NOT generated by an LLM" likha hai) ab khoobsurat hai: maximized space
   window, 3 sawal, auto-clear, rangeen feedback, aakhir mein Congratulations + sitare + confetti.

### Ek asal bug jo testing mein pakra
- Exe ke andar Tk window ko band kar ke **dobara** banana kabhi kabhi Windows par crash karta tha.
  Hal: tests mein poore session ke liye **ek hi** Tk window; yeh qaida AI ke prompt mein bhi daal diya taake
  generated game ke tests bhi crash na hon. 8 dafa exe mein chala kar confirm kiya — sab green.

---

## Phase 5 — Asal DeepSeek runs (4 dafa) aur agent ko behtar banana

### Sab se ahem usool
- **Generated game ko kabhi haath se theek nahi kiya.** Har run ke baad asal window khol kar dekha; jo kharabi mili,
  us ke liye **agent** ko behtar banaya (rule, tool, ya verification) aur dobara chalaya. Professor ke liye ye sab
  se mazboot baat hai: "main ne AI ka code nahi, AI agent ko behtar kiya".

### Chaar runs ki kahani (kul kharcha ≈ $0.55)
| Run | Kya hua | Agent mein kya badla |
|---|---|---|
| 1 ($0.10) | Tests pass, lekin window mein sitare/title gayab (canvas width=1 par draw hua) | **UI probe**: harness asal window khol kar har screen check karta hai |
| 2 ($0.10) | Pehli koshish mein pass; ghalat jawab par **agle** sawal ka jawab dikhata | **Rule 10**: message ka data state badalne se *pehle* utha lo + test |
| 3 ($0.13) | Probe ne bahar gire buttons pakre → **agent ne khud fix round mein theek kiya** | pack/grid rule, poora-round smoke test, `delete_file` tool |
| 4 ($0.14) | 5 rounds khel kar 0 errors; feedback sahi | final example |

### Kuch concepts jo video/interview mein bolne hain
- **Prompt caching:** har request ka shuru ka hissa same → DeepSeek ~98% tokens cache se deta hai → 1 run ≈ 10–15 cents.
- **Resume:** run 1 aur 4 limit par ruke, `state.json` se wahin se dobara chale — Claude Code / claw-code jaisa.
- **Error recovery:** model ne ghalat JSON / missing `path` bheja → crash nahi, error wapas model ko → khud theek.
- **Sandbox zinda saboot:** run 4 mein model ne `/tmp/debug.py` likhna chaha → "Absolute paths are not allowed".
- **UI design brief:** plan mein agent khud tay karta hai kaun use karega, kaun se rang/fonts — Tic-Tac-Toe aur
  library app ke liye alag look.

## Phase 6 — README, Architecture, Video script
- `README.md`: download, quick start, diagram, **mechanism table** (16 mechanisms), web→desktop, input issues,
  real runs ka imaandar khulasa, **known limitations**, build/test, credits.
- `docs/ARCHITECTURE.md`: flow + sequence diagrams, modules, safety layers.
- `docs/VIDEO_SCRIPT.md`: 6 minute ka script (kya dikhana, kya bolna) + backup plan (Replay).

### Interview line
"Main ne 4 asal runs kiye, har run ke baad window khud dekhi, aur jo bhi kharabi mili use agent ke rules aur
verification mein generic tareeqe se theek kiya — aakhri run mein 5 poore rounds bina kisi error ke chale."

### Run 5 (final) — kya seekha
- Probe ab **do sizes** (1280×800 aur 1100×750) par check karta hai, kata hua button text aur "input ke saath button
  nahi" bhi pakarta hai → Run 5 ka game choti screen par bhi poora fit, typed sawal ke saath **Check** button.
- Run ke dauran verify FAILED aaya — lekin aakhri "masle" asal mein **mere probe ki ghalti** thi (scroll hone wali
  list ki rows ko bahar gina). Imaandari: probe theek kiya, test likha, aur **wahi code bina API ke dobara verify**
  kiya → sab pass. Asal RUN_REPORT waisa hi rakha; dobara-verify ka saboot alag file mein.
- Sabaq (interview ke liye): "Automated checker bhi software hai — us ke false positives bhi test aur fix karne
  parte hain."

## Run 7 (aap ka GUI run) aur write_files ka masla

- **Run 7 final example kyun:** yeh aap ne khud exe ke GUI se chalaya, bina profile ke. Verify 2 fix rounds ke baad
  PASSED hua (agent ne khud "Back to Menu" button wali problems theek ki). 25 seed sawal, har round random, 1000 generated
  sawal check kiye — jama/tafreeq/zarb, compare aur simplify sab sahi. Code haath se nahi chheda.
- **Kamzoriyan (known limitations mein likh di):** khelte waqt score/progress nazar nahi aata; admin ka Kind field
  free text hai; "equivalent" sawal bekaar hain kyunke `Fraction(6, 8)` khud `3/4` ban jata hai, is liye jawab sawal
  jaisa hi dikhta hai; admin mein naya sawal restart ke baad hi aata hai.
- **write_files masla:** model pehle `"content"` (lambi file) likhta tha aur `"path"` bhool jata tha — run 7 mein 12 mein
  se 6 calls aisi thi, aur har dafa poori file dobara bhejni padti thi (paise aur requests zaya). **Hal:** ab `files` ek
  object hai jis ki *key hi path hai*: `{"ui/theme.py": "...code..."}`. Key ke baghair value likhi hi nahi ja sakti, is
  liye path gum nahi ho sakta. Purana list wala tareeqa bhi chalta hai (pichhle transcripts/replay ke liye).

## Run 8 (aakhri run) — intro movie, admin PIN

- **Naye generic rules:** spec mein jo screen/scene ka naam hai woh banana zaroori hai; "movie/animation" likha ho to
  Canvas par 5–10 second ki chalti hui animation, Skip button ke saath; admin jaisa role ho to window ke andar PIN screen.
  Harness spec se khud naam nikalta hai ("introductory movie", "Admin") aur UI probe check karta hai ke cheezein
  waqai hil rahi hain, Skip button hai, aur PIN wala chhupa (`*`) input hai.
- **Nateeja:** 58 requests, $0.159, verify PASSED. Intro mein sitare aur rocket chalte hain (5 s), PIN 1234 se admin
  khulta hai, ghalat PIN par laal error. Khelte waqt "1 / 10 Score: 0" nazar aata hai. write_files ka ek bhi error nahi.
- **Kamzoriyan:** generated "equivalent" sawal phir bekaar (jawab sawal jaisa), "which is larger" mein faltu options,
  aur "lowest terms" mein 4/6 bhi sahi maan liya jata hai. Is ke liye naya generic rule add kiya (abhi run se test nahi hua).

## Run 9 — admin ki list, Add, Edit, Delete

- **Naya rule:** agar spec mein koi role data update/manage/maintain karta ho to us ki screen par saare records ki list
  (seed samet) aur Add, Edit, Delete — har ek ka test. UI probe check karta hai ke seed data ho to list khaali na ho, aur
  teeno buttons maujood hon. Aap ke GUI run 0038 (sirf Add) ko yeh check pakadta hai; Run 7 aur 8 pass.
- **Run 9:** beech mein balance khatam (402) → top up → resume → aap ne roka → 3 baje khud resume → VERIFY PASSED.
  59 requests, asal kharcha ≈ $0.38 (kuch hissa peak par).
- **Nateeja:** admin mein 22 seed sawal nazar aate hain, Add/Edit/Delete teeno chalte hain; intro movie (8 s, Skip);
  PIN **4321** (Run 8 mein 1234 tha — README mein likha hai); sab jawab sahi, equivalent aur lowest-terms ab theek.
- **Kamzoriyan:** "identify" sawal mein jawab sawal mein likha hota hai; compare mein faltu options; admin ka success
  message refresh se mit jata hai; menu mein Exit nahi.

## Architecture-only variant (research ke liye, alag folder)

- **Kyun:** asal project mein humne bahar se bahut si requirements daali thi (intro movie, PIN, admin list, 20 seed sawal,
  bachon wala look…). Is se game behtar bana, lekin yeh sabit nahi hota ke AI **sirf naqshe** se kitna achha banata hai.
- **Kya hataya:** UI aur app ke saare rules, task profile, spec se banne wali checklist, aur spec.json ka woh hissa jis
  mein maine khud "SQLite" likha tha (yeh asal mein model ko data store bata deta tha — aap ki report ka PostgreSQL→SQLite
  wala farq is wajah se bhi ho sakta tha).
- **Kya rakha:** sirf professor ki shartein (desktop app, Python stdlib, code + requirements.txt + README + tests) aur agent
  ke kaam karne ke tareeqe (tools, plan → likhna → verify → fix).
- **Verify:** sirf "chalta hai ya nahi": compile, agent ke apne tests, imports, aur main.py 3 second chala kar dekhna ke
  crash to nahi hota. Design/layout ke checks hata diye.
- **Switch:** "deviation record karo" ON/OFF. ON par agent ko kaha jata hai ke naqshe se jahan hata, wahan DESIGN_DECISIONS.md
  mein wajah likhe; OFF par kuch nahi kaha jata. Dono runs se aap ki report ke OP2 ka sawal check ho sakta hai.
- **GitHub:** is folder ka koi remote nahi; push ho hi nahi sakta. Asal project aur GitHub waise hi hain.

## Study runs b1–b3 (2026-11-09) — asaan alfaaz mein

- **Kya kiya:** Agent B (sirf naqsha) ko teen dafa chalaya, har dafa naye khali folder mein. Agent ko beech mein
  bilkul nahi badla (freeze). Teeno runs pass hue, har run takreeban $0.045 ka. Balance $0.77 se $0.63 reh gaya.
- **Saboot (evidence):** har run ki video (agent ka GUI), har phase ka screenshot, har event ka log; phir ek bot ne
  har game 80 qadam tak khela — us ki video, subtitles (har click likha hua) aur har screen ki tasveer.
- **Bot kaisa hai:** game ke baare mein kuch nahi jaanta; jo button/field screen par hai wahi dabata hai, jaise
  ek naya user. Sab games (A ka bhi) bilkul ek hi bot se khele gaye, taake muqabla barabar ho.
- **Sab se aham nateeja (OP2):** naqsha PostgreSQL, Node.js, Docker waghera kehta hai; teeno runs ne SQLite aur
  desktop banaya, lekin README/AGENT_NOTES mein **ek bhi** deviation nahi likha (0/12). Agent A ne likha tha kyunke
  us ke prompt mein likhna zaroori tha. Yani hidayat na ho to deviations chhup jaate hain.
- **Jo checks ne nahi pakra:** b1 mein intro par click kaam nahi karta (sirf key), b2 mein Edit nahi hai aur radio
  buttons sab bhare dikhte hain, b3 mein login ka component hai magar istemaal nahi hota — Admin sab ke liye khula.
  Agent ke tests sirf apna code check karte hain, naqsha nahi.
