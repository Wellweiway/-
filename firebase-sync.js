
(function () {
  "use strict";

  const box = document.createElement("div");
  box.id = "cloudSyncStatus";
  box.style.cssText =
    "margin:10px 12px;padding:10px 14px;border:1px solid #d8c9ad;border-radius:12px;background:#fffaf0;color:#554b3d;font-size:13px";
  box.textContent = "雲端同步：準備連線中…";

  const header = document.querySelector("header");
  if (header) header.insertAdjacentElement("afterend", box);

  const say = (message, error) => {
    box.textContent = "雲端同步：" + message;
    box.style.color = error ? "#b3261e" : "#554b3d";
  };

  const keys = ["hd", "wl", "tg"];
  let db = null;
  let uid = null;
  let ready = false;
  let applying = false;
  let timer = null;

  function readLocal() {
    return {
      hd: JSON.parse(localStorage.getItem("hd") || "[]"),
      wl: JSON.parse(localStorage.getItem("wl") || "[]"),
      tg: JSON.parse(localStorage.getItem("tg") || "{}")
    };
  }

  function valid(p) {
    return p &&
      Array.isArray(p.hd) &&
      Array.isArray(p.wl) &&
      p.tg &&
      typeof p.tg === "object" &&
      !Array.isArray(p.tg);
  }

  async function saveCloud() {
    if (!ready || applying) return;

    try {
      await db.collection("users").doc(uid)
        .collection("private").doc("appData")
        .set({
          payload: readLocal(),
          updatedAt: firebase.firestore.FieldValue.serverTimestamp()
        });

      say("同步成功");
    } catch (e) {
      console.error(e);
      say("同步失敗，手機資料仍保留，請檢查網路或資料庫規則", true);
    }
  }

  function scheduleSave() {
    if (!ready || applying) return;
    clearTimeout(timer);
    timer = setTimeout(saveCloud, 800);
  }

  async function start() {
    try {
      if (!window.firebaseConfig || !window.firebase) {
        throw new Error("Firebase 設定或 SDK 未載入");
      }

      const app = firebase.apps.length
        ? firebase.app()
        : firebase.initializeApp(window.firebaseConfig);

      db = app.firestore();

      await app.auth().signInAnonymously();
      uid = app.auth().currentUser.uid;

      const ref = db.collection("users").doc(uid)
        .collection("private").doc("appData");

      const snapshot = await ref.get();

      applying = true;

      if (snapshot.exists && valid(snapshot.data().payload)) {
        const p = snapshot.data().payload;

        keys.forEach(key => {
          localStorage.setItem(key, JSON.stringify(p[key]));
        });

        say("已載入雲端資料");
      } else {
        await ref.set({
          payload: readLocal(),
          updatedAt: firebase.firestore.FieldValue.serverTimestamp()
        });

        say("首次備份完成");
      }

      applying = false;
      ready = true;

      // 更新原 App 畫面
      if (typeof window.rw === "function") window.rw();
      if (typeof window.rh === "function") window.rh();
      if (typeof window.rdv === "function") window.rdv();

    } catch (e) {
      applying = false;
      console.error("Firebase sync error:", e);
      say("連線失敗；手機資料沒有被清除。請檢查設定", true);
    }
  }

  // 監聽原 App 對 localStorage 的寫入
  const originalSetItem = Storage.prototype.setItem;

  Storage.prototype.setItem = function (key, value) {
    originalSetItem.call(this, key, value);

    if (this === localStorage && keys.includes(key)) {
      scheduleSave();
    }
  };

  start();
})();
