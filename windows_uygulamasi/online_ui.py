# -*- coding: utf-8 -*-
"""Online düello ekranları (MainFrame'e karışım olarak eklenir)."""
import random
import time
import webbrowser

import wx

import online as ol
import yasak
import yasal

CONTACT_URL = yasal.SITE_URL + "/iletisim.html"

LETTERS = "ABCD"
ONLINE_SCREENS = ("ovs", "ogame", "osetup", "owait", "oresult", "odisc")
WAIT_MESSAGE = "Lütfen bekleyin, ufak birkaç işlem yapıyoruz…"


def spaced(code):
    return " ".join(code)


class OnlineMixin:
    # ------------------------------------------------------------ başlangıç / kapanış
    def online_init(self):
        self.sess = None
        self.duel = None
        self.my_name = str(self.cfg.d.get("ad", "") or "")
        self.opp_name = "Rakip"
        self.opp_pid = ""
        self.guarding = False
        self.is_host = False
        self.chat = []
        self.post_game = False
        self.my_rematch = False
        self.opp_rematch = False
        self.in_setup = False
        self.o_status_tc = None
        self.o_note_tc = None
        self.o_name_tc = None
        self.o_code_tc = None
        self.o_err = None
        self.o_players = None
        self.o_wait_tc = None
        self.o_count = None
        self.o_timer_lbl = None
        self.o_gauge = None
        self.o_radio = None
        self.o_rm_tc = None
        self.o_rm_btn = None
        self.o_warned = False
        self.o_last_tick = -1

    @property
    def in_match(self):
        return bool(self.sess and self.sess.matched)

    def online_close(self):
        s, self.sess = self.sess, None
        self.duel = None
        self.in_setup = False
        self.post_game = False
        if s:
            s.close()

    # ------------------------------------------------------------ ad ve menü
    def show_terms_gate(self):
        self.screen = "tgate"
        self.new_screen("Online - kullanım şartları")
        self.add_heading("Kullanım Şartları")
        self.add_text("Online oynamak için Kullanım Şartları'nı ve Gizlilik Politikası'nı kabul etmelisin.", 14)
        tc = self.add_readonly("Kullanım Şartları", yasal.TERMS_TEXT, height=300, size=14)
        self.add_button("Kabul ediyorum", lambda e: self.go(self.terms_accept), primary=True)
        self.add_button("Gizlilik Politikası'nı oku", lambda e: self.go(self.show_legal, "privacy", self.show_terms_gate))
        self.add_button("Kabul etmiyorum (ana menü)", lambda e: self.go(self.show_home))
        self.finish_layout()
        tc.SetFocus()
        self.say("Online oynamadan önce Kullanım Şartları'nı oku. Kabul ediyorsan Kabul ediyorum düğmesine bas.")

    def terms_accept(self):
        self.cfg.d["sartlar"] = yasal.TERMS_VERSION
        self.cfg.save()
        self.show_online_name()

    def show_online_name(self, error=""):
        self.online_close()
        if self.cfg.d.get("sartlar") != yasal.TERMS_VERSION:
            self.show_terms_gate()
            return
        self.screen = "oname"
        self.new_screen("Online - kullanıcı adı")
        self.add_heading("Online Oyna")
        self.add_text("Rakibin seni bu adla görecek. Oyuncu kimliğin: %s. İtiraz ve bildirimlerde bu kimlik kullanılır." % self.pid, 14)
        lab = wx.StaticText(self.panel, label="Kullanıcı adınız")
        lab.SetFont(self.font(12))
        self.col.Add(lab, 0, wx.TOP, 6)
        self.o_name_tc = wx.TextCtrl(self.panel, value=self.my_name, style=wx.TE_PROCESS_ENTER)
        self.o_name_tc.SetMaxLength(20)
        self.o_name_tc.SetFont(self.font(16))
        self.o_name_tc.SetName("Kullanıcı adınız")
        self.col.Add(self.o_name_tc, 0, wx.EXPAND | wx.BOTTOM, 8)
        self.o_err = self.add_text(error, 13)
        self.add_button("Devam", lambda e: self._name_ok(), primary=True)
        self.add_button("Geri", lambda e: self.go(self.show_home))
        self.o_name_tc.Bind(wx.EVT_TEXT_ENTER, lambda e: self._name_ok())
        self.finish_layout()
        self.o_name_tc.SetFocus()
        self.say("Online oyna. Kullanıcı adını yaz ve Enter'a bas." + (" " + error if error else ""))

    def _name_ok(self):
        v = self.o_name_tc.GetValue().strip()
        if not v:
            self.o_err.SetLabel("Lütfen bir ad yaz.")
            self.say("Lütfen bir ad yaz.")
            self.o_name_tc.SetFocus()
            return
        self.my_name = v[:20]
        self.cfg.d["ad"] = self.my_name
        self.cfg.save()
        self.go(self.online_guard, self.show_online_menu)

    # ------------------------------------------------------------ yasak denetimi
    def online_guard(self, fn, *args):
        """Yasak listesini sorar; yasaklı değilsek (ya da sunucuya ulaşılamazsa) fn çalışır."""
        if self.guarding:
            return
        self.guarding = True
        self.say("Kontrol ediliyor…", interrupt=False)

        def done(res, err):
            self.guarding = False
            ok, bans = res if res else (False, {})
            if ok:
                self.ban_map = bans
            if self.pid in self.ban_map:
                self.show_banned(self.ban_map[self.pid])
            else:
                fn(*args)
        self.run_bg(yasak.fetch_bans, done)

    def show_banned(self, until):
        self.online_close()
        self.screen = "obanned"
        self.new_screen("Online erişim kapalı")
        self.add_heading("Online erişimin kapalı")
        if until:
            when = time.strftime("%d.%m.%Y %H:%M", time.localtime(until / 1000.0)) + " tarihine kadar"
        else:
            when = "süresiz olarak"
        text = ("Bu cihazın online oynaması %s kapatıldı. Tek başına, günlük meydan okuma ve çok oyunculu "
                "modlar kullanılabilir. Yanlış olduğunu düşünüyorsan oyuncu kimliğinle itiraz edebilirsin.\n"
                "Oyuncu kimliğin: %s" % (when, self.pid))
        tc = self.add_readonly("Bilgi", text, height=160, size=16)
        self.add_button("İtiraz / iletişim (tarayıcıda açılır)", lambda e: webbrowser.open(CONTACT_URL))
        self.add_button("Ana menü", lambda e: self.go(self.show_home), primary=True)
        self.finish_layout()
        tc.SetFocus()
        self.say("Online erişimin kapalı. " + text.replace("\n", " "))

    # ------------------------------------------------------------ rakibi bildir
    def report_opponent(self):
        if not (self.opp_pid or self.opp_name != "Rakip"):
            self.say("Bildirilecek bir rakip yok.")
            return
        labels = [k[1] for k in yasak.KINDS]
        dlg = wx.SingleChoiceDialog(self, "%s adlı rakibi neden bildiriyorsun?" % self.opp_name,
                                    "Rakibi bildir", labels)
        self.say("Rakibi bildir. Nedeni seç ve Enter'a bas.")
        if dlg.ShowModal() != wx.ID_OK:
            dlg.Destroy()
            return
        kind = yasak.KINDS[dlg.GetSelection()][0]
        dlg.Destroy()
        d2 = wx.TextEntryDialog(self, "Açıklama (isteğe bağlı, en çok 300 karakter):", "Rakibi bildir")
        try:
            d2.SetMaxLength(300)
        except Exception:
            pass
        ok = d2.ShowModal() == wx.ID_OK
        note = d2.GetValue().strip()
        d2.Destroy()
        if not ok:
            return
        self.say("Bildirim gönderiliyor…", interrupt=False)
        pid, name = self.opp_pid, self.opp_name

        def done(res, err):
            good, msg = res if res else (False, "Bağlantı kurulamadı.")
            self.say("Bildirimin yöneticiye iletildi. Teşekkürler." if good else "Bildirim gönderilemedi: %s" % msg)
        self.run_bg(lambda: yasak.send_report(self.pid, pid, name, kind, note), done)

    def show_online_menu(self, error=""):
        self.online_close()
        self.screen = "omenu"
        self.new_screen("Online - menü")
        self.add_heading("Online düello")
        self.add_text("%s olarak oynuyorsun. 10 soru, hızlı ve doğru bilen daha çok puan alır." % self.my_name, 14)
        self.add_text("Sitedeki oyuncularla ve masaüstü uygulamasını kullananlarla eşleşebilirsin.", 12)
        self.add_text(error, 13)
        first = self.add_button("Rastgele rakip bul", lambda e: self.go(self.online_guard, self.start_random), primary=True)
        self.add_button("Özel oda kur (arkadaşına kod ver)", lambda e: self.go(self.online_guard, self.start_host))
        self.add_button("Kodla odaya katıl", lambda e: self.go(self.show_join_code))
        self.add_button("Adı değiştir", lambda e: self.go(self.show_online_name))
        self.add_button("Geri", lambda e: self.go(self.show_home))
        self.finish_layout()
        first.SetFocus()
        self.say("Online düello menüsü. " + error)

    def show_join_code(self, error=""):
        self.screen = "ojoin"
        self.new_screen("Online - odaya katıl")
        self.add_heading("Odaya katıl")
        lab = wx.StaticText(self.panel, label="Oda kodu (6 rakam)")
        lab.SetFont(self.font(12))
        self.col.Add(lab, 0, wx.TOP, 6)
        self.o_code_tc = wx.TextCtrl(self.panel, style=wx.TE_PROCESS_ENTER)
        self.o_code_tc.SetMaxLength(6)
        self.o_code_tc.SetFont(self.font(20))
        self.o_code_tc.SetName("Oda kodu")
        self.col.Add(self.o_code_tc, 0, wx.EXPAND | wx.BOTTOM, 8)
        self.o_err = self.add_text(error, 13)
        self.add_button("Katıl", lambda e: self._join_ok(), primary=True)
        self.add_button("Geri", lambda e: self.go(self.show_online_menu))
        self.o_code_tc.Bind(wx.EVT_TEXT_ENTER, lambda e: self._join_ok())
        self.finish_layout()
        self.o_code_tc.SetFocus()
        self.say("Odaya katıl. Arkadaşının verdiği 6 haneli kodu yaz." + (" " + error if error else ""))

    def _join_ok(self):
        code = self.o_code_tc.GetValue().strip().replace(" ", "")
        if len(code) != 6 or not code.isdigit():
            self.o_err.SetLabel("Kod 6 rakamdan oluşmalı.")
            self.say("Kod 6 rakamdan oluşmalı.")
            self.o_code_tc.SetFocus()
            return
        self.go(self.online_guard, self.start_join, code)

    # ------------------------------------------------------------ bağlantı başlatma
    def _new_session(self):
        self.online_close()
        holder = {}

        def emit(ev, **kw):
            wx.CallAfter(self.on_sess_event, holder.get("s"), ev, kw)

        s = ol.Session(lambda on_msg: ol.MqttTransport(on_msg), emit, self.my_name, self.pid, self.ban_map)
        holder["s"] = s
        self.sess = s
        self.chat = []
        self.opp_name = "Rakip"
        self.opp_pid = ""
        self.my_rematch = self.opp_rematch = False
        return s

    def start_random(self):
        s = self._new_session()
        self.show_online_wait("Rakip aranıyor…", "Sunucuya bağlanılıyor…")
        s.start_random()

    def start_host(self):
        s = self._new_session()
        self.show_online_wait("Oda kuruluyor…", "Sunucuya bağlanılıyor…")
        s.host_room()

    def start_join(self, code):
        s = self._new_session()
        self.show_online_wait("Odaya katılınıyor…", "Sunucuya bağlanılıyor…")
        s.join_room(code)

    def show_online_wait(self, title, sub, code=None, cancel_label="İptal"):
        self.screen = "owait"
        self.new_screen("Online - bekleniyor")
        self.add_heading(title)
        self.o_wait_tc = self.add_readonly("Durum", sub or title, height=80, size=16)
        if code:
            self.add_readonly("Oda kodu", code, height=80, size=32, bold=True)
            self.add_button("Kodu panoya kopyala", lambda e: self._copy(code))
        self.wait_gauge = wx.Gauge(self.panel, range=100, style=wx.GA_HORIZONTAL)
        self.col.Add(self.wait_gauge, 0, wx.EXPAND | wx.TOP, 6)
        self.add_button(cancel_label, lambda e: self.go(self.online_cancel))
        self.finish_layout()
        self.wait_timer.Start(80)
        self.o_wait_tc.SetFocus()
        self.say("%s %s" % (title, sub if sub != title else ""))
        self.later(2400, self._wait_ping)

    def _wait_ping(self):
        if self.screen == "owait":
            self.sounds.play("bekle")
            self.later(2400, self._wait_ping)

    def _copy(self, code):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(code))
            wx.TheClipboard.Close()
            self.say("Kod panoya kopyalandı.")

    def online_cancel(self):
        self.show_online_menu()

    # ------------------------------------------------------------ oturum olayları
    def on_sess_event(self, sess, ev, kw):
        if self.closing or sess is None or sess is not self.sess:
            return
        if ev == "status":
            if self.screen == "owait" and self.o_wait_tc:
                self.o_wait_tc.SetValue(kw["text"])
            self.say(kw["text"], interrupt=False)
        elif ev == "room_ready":
            code = kw["code"]
            self.show_online_wait("Oda hazır", "Arkadaşına bu kodu ver. Rakip bağlanınca oyun kendiliğinden başlar.",
                                  code=code, cancel_label="Odayı kapat")
            self.say("Oda kodu: %s. Tekrar duymak için kod kutusuna odaklan." % spaced(code), interrupt=False)
        elif ev == "error":
            self.show_online_menu(error=kw["text"])
        elif ev == "matched":
            self.opp_name = kw["opp_name"]
            self.opp_pid = kw.get("opp_pid", "")
            self.is_host = kw["role"] == "host"
            self.sounds.play("bulundu")
            self.say("Rakip bulundu: %s." % self.opp_name)
            if self.is_host:
                self.later(900, self.host_setup)
            else:
                self.guest_wait()
        elif ev == "msg":
            self.on_online_data(kw["data"])
        elif ev == "left":
            self.on_opp_left()

    # ------------------------------------------------------------ oyun ayarı
    def host_setup(self):
        if not self.in_match:
            return
        self.in_setup = True
        self.screen = "osetup"
        self.new_screen("Online - oyun ayarı")
        self.add_heading("Oyun ayarı")
        self.add_text("Rakibin: %s. Oda yöneticisi sensin." % self.opp_name, 14)
        choices = ["Süresiz" if v == 0 else "Soru başına %d saniye" % v for v in ol.O_TIMES]
        self.o_radio = wx.RadioBox(self.panel, label="Her soru için süre", choices=choices,
                                   majorDimension=2, style=wx.RA_SPECIFY_COLS)
        self.o_radio.SetFont(self.font(14))
        pref = self.cfg.d.get("osure", 20)
        self.o_radio.SetSelection(ol.O_TIMES.index(pref) if pref in ol.O_TIMES else 0)
        self.col.Add(self.o_radio, 0, wx.EXPAND | wx.BOTTOM, 10)
        self.add_text("Süreli oyunda doğruyu ne kadar hızlı bilirsen o kadar çok puan alırsın. "
                      "Süresizde her doğru %d puan." % ol.O_BASE, 12)
        self.add_button("Oyunu başlat", lambda e: self.go(self.host_start_pressed), primary=True)
        self.add_button("Odadan ayrıl", lambda e: self.go(self.show_online_menu))
        self.finish_layout()
        self.o_radio.SetFocus()
        self.sess.send({"t": "setup"})
        self.say("Oyun ayarı. Rakibin %s. Her soru için süreyi seç, sonra Oyunu başlat düğmesine bas. "
                 "Sohbet için S tuşuna bas." % self.opp_name)

    def host_start_pressed(self):
        if not self.in_match:
            return
        sel = self.o_radio.GetSelection() if self.o_radio else 0
        qt = ol.O_TIMES[max(0, sel)]
        self.cfg.d["osure"] = qt
        self.cfg.save()
        self.sess.send({"t": "preparing"})
        self.show_wait(WAIT_MESSAGE)
        self.run_bg(self.load_questions_fn, lambda res, err: self._host_questions(qt, res, err))

    def _host_questions(self, qt, res, err):
        if not self.in_match:
            return
        if res and not err:
            self.pool, self.source = res["pool"], res["source"]
        try:
            qs = self.build_online_qs(ol.O_ROUNDS)
        except Exception:
            self.say("Sorular hazırlanamadı.")
            self.host_setup()
            return
        self.duel = ol.Duel(qs, qt)
        self.sess.send({"t": "start", "qs": qs, "qtime": qt})
        self.begin_online()

    def build_online_qs(self, n):
        if len(self.pool) < n:
            raise ValueError("yetersiz soru")
        out = []
        for q in random.sample(self.pool, n):
            opts = [{"t": t, "c": i == q["ans"]} for i, t in enumerate(q["opts"])]
            random.shuffle(opts)
            out.append({"cat": q["cat"], "q": q["q"], "o": opts, "e": q["exp"]})
        return out

    def guest_wait(self, text=None):
        self.in_setup = True
        text = text or ("%s oyunu ayarlıyor." % self.opp_name)
        self.show_online_wait(text, "Oyun birazdan başlayacak. Sohbet için S tuşuna bas.",
                              cancel_label="Odadan ayrıl")

    # ------------------------------------------------------------ gelen veriler
    def on_online_data(self, d):
        t = d.get("t")
        i = d.get("i")
        if t == "chat":
            text = str(d.get("text", ""))[:240]
            name = str(d.get("name") or self.opp_name)[:20]
            if text:
                self.chat.append("%s: %s" % (name, text))
                self.sounds.play("mesaj_al")
                self.say("%s: %s" % (name, text), interrupt=False)
        elif t == "rematch":
            self.opp_rematch = True
            if self.post_game:
                self._set_rm_status("%s rövanş istiyor. Kabul etmek için Rövanş düğmesine bas." % self.opp_name)
            self.try_rematch()
        elif t == "setup" and not self.is_host:
            if self.post_game or not self.in_setup:
                self.post_game = False
                self.duel = None
                self.sounds.play("bulundu")
                self.guest_wait()
        elif t == "preparing" and not self.is_host:
            if self.screen == "owait" and self.o_wait_tc:
                self.o_wait_tc.SetValue("Sorular hazırlanıyor…")
        elif t == "start" and not self.is_host:
            qs = ol.valid_questions(d.get("qs"))
            qt = d.get("qtime")
            if qs and qt in ol.O_TIMES and len(qs) >= ol.O_ROUNDS:
                self.duel = ol.Duel(qs, qt)
                self.begin_online()
        elif t == "ready" and self.duel and isinstance(i, int) and 0 <= i < 60:
            self.duel.opp_ready[i] = True
            if self.screen == "ogame" and self.o_note_tc and i == self.duel.round + 1 \
                    and not self.duel.my_ready.get(i):
                self.o_note_tc.SetValue("%s hazır." % self.opp_name)
            self.try_advance()
        elif t == "ans" and self.duel and isinstance(i, int) and 0 <= i < 60:
            self.duel.opp_answer(i, d.get("k"), d.get("ms"))
            if self.duel.round == i and self.duel.phase == "q":
                if i in self.duel.my:
                    self.reveal_round(i)
                elif self.o_status_tc:
                    self.o_status_tc.SetValue("Rakip cevapladı.")
                    self.say("%s cevapladı." % self.opp_name, interrupt=False)
        elif t == "extra" and self.duel and isinstance(i, int) and 0 <= i < 60:
            q = ol.valid_question(d.get("q"))
            if q:
                self.duel.qs[i] = q
                self.try_advance()

    # ------------------------------------------------------------ düello başlangıcı
    def begin_online(self):
        self.in_setup = False
        self.post_game = False
        self.my_rematch = self.opp_rematch = False
        self.show_vs()

    def show_vs(self):
        d = self.duel
        self.screen = "ovs"
        self.new_screen("Online - başlıyor")
        self.add_heading("%s  VS  %s" % (self.my_name, self.opp_name))
        role = "Oda yöneticisi sensin. " if self.is_host else "%s oda yöneticisi. " % self.opp_name
        if d.qtime:
            rule = "%d soru var. Her soru için %d saniyen var. Doğruyu ne kadar hızlı bilirsen o kadar çok puan alırsın." \
                   % (ol.O_ROUNDS, d.qtime)
        else:
            rule = "%d soru var. Süre sınırı yok. Her doğru cevap %d puan." % (ol.O_ROUNDS, ol.O_BASE)
        keys = " Kısayollar: 1 ile 4 arası şık seçer, C soruyu okur, T süreyi, P puanı söyler, S sohbet mesajı yazar, H sohbeti okur."
        self.add_text(role + rule + keys, 14)
        self.o_count = wx.StaticText(self.panel, label="3")
        self.o_count.SetFont(self.font(48, True))
        self.col.Add(self.o_count, 0, wx.TOP, 10)
        self.finish_layout()
        self.sounds.play("start")
        self.say("%sRakibin %s. %s Başlıyor." % (role, self.opp_name, rule + keys))
        n = [3]

        def step():
            if self.duel is not d or self.screen != "ovs" or d.finished:
                return
            n[0] -= 1
            if n[0] > 0:
                self.sounds.play("tick")
                if self.o_count:
                    self.o_count.SetLabel(str(n[0]))
                self.later(1000, step)
            else:
                if self.o_count:
                    self.o_count.SetLabel("…")
                self.send_ready(0)

        self.later(1000, step)

    def send_ready(self, n):
        d = self.duel
        if not d:
            return
        d.my_ready[n] = True
        if self.sess:
            self.sess.send({"t": "ready", "i": n})
        self.try_advance()

    def try_advance(self):
        d = self.duel
        if d and not d.finished and d.can_advance():
            self.start_round(d.round + 1)

    # ------------------------------------------------------------ soru
    def players_text(self):
        d = self.duel
        return "%s: %d puan, %s: %d puan" % (self.my_name, d.my_pts, self.opp_name, d.opp_pts)

    def online_question_speech(self, with_time=False):
        d = self.duel
        q = d.qs[d.round]
        extra = d.round >= ol.O_ROUNDS
        head = "Altın soru." if extra else "Soru %d / %d." % (d.round + 1, ol.O_ROUNDS)
        opts = ", ".join("%s: %s" % (LETTERS[k], o["t"]) for k, o in enumerate(q["o"]))
        s = "%s Kategori: %s. %s Seçenekler: %s." % (head, q["cat"], q["q"], opts)
        if with_time:
            s += " " + self.online_time_text()
        return s

    def online_time_text(self):
        d = self.duel
        if not d or not d.qtime:
            return "Süre sınırı yok."
        if d.phase == "q" and not d.locked:
            return "Kalan süre: %d saniye." % max(0, int(d.deadline - time.monotonic() + 0.999))
        return "Bu soru için süre durdu."

    def start_round(self, n):
        d = self.duel
        d.begin_round(n, time.monotonic())
        q = d.qs[n]
        extra = n >= ol.O_ROUNDS
        self.screen = "ogame"
        self.new_screen("Online - %s" % ("altın soru" if extra else "soru %d" % (n + 1)))
        self.o_note_tc = None
        if extra:
            self.sounds.play("altin")
        elif n > 0:
            self.sounds.play("next")
        title = "Altın soru: eşitlik bozulana kadar" if extra else "Soru %d / %d" % (n + 1, ol.O_ROUNDS)
        h = self.add_text("%s — %s" % (title, q["cat"]), 14)
        h.SetFont(self.font(14, True))
        self.o_players = self.add_text(self.players_text(), 13)
        self.o_timer_lbl = self.o_gauge = None
        if d.qtime:
            self.o_timer_lbl = wx.StaticText(self.panel, label="Kalan süre: %d saniye" % d.qtime)
            self.o_timer_lbl.SetFont(self.font(13))
            self.col.Add(self.o_timer_lbl, 0, wx.BOTTOM, 4)
            self.o_gauge = wx.Gauge(self.panel, range=1000, style=wx.GA_HORIZONTAL)
            self.o_gauge.SetValue(1000)
            self.col.Add(self.o_gauge, 0, wx.EXPAND | wx.BOTTOM, 8)
        qtext = "%s\n%s" % (q["cat"], q["q"])
        if not self.speaker.available:
            qtext = self.online_question_speech()
        self.q_ctrl = self.add_readonly("Soru", qtext, height=110, size=18, bold=True)
        self.opt_btns = []
        for k in range(4):
            b = wx.Button(self.panel, label="%s: %s" % (LETTERS[k], q["o"][k]["t"]))
            b.SetFont(self.font(15))
            b.SetMinSize((-1, 50))
            b.SetWindowStyleFlag(wx.BU_LEFT)
            b.Bind(wx.EVT_BUTTON, lambda e, kk=k: self.online_pick(kk))
            self.col.Add(b, 0, wx.EXPAND | wx.BOTTOM, 6)
            self.opt_btns.append(b)
        self.o_status_tc = self.add_readonly(
            "Durum", "Rakip cevapladı." if n in d.opp else "Rakip düşünüyor…", height=50, size=14)
        self.fb_col = wx.BoxSizer(wx.VERTICAL)
        self.col.Add(self.fb_col, 0, wx.EXPAND | wx.TOP, 6)
        self.finish_layout()
        self.q_ctrl.SetFocus()
        speech = self.online_question_speech(with_time=bool(d.qtime))
        self.later(250, self._speak_round, d, n, speech)
        self.o_warned = False
        self.o_last_tick = -1
        if d.qtime:
            self.game_timer.Start(200)

    def _speak_round(self, d, n, text):
        if self.duel is d and d.round == n:
            self.say(text)

    def on_online_timer(self):
        d = self.duel
        if not d or d.phase != "q" or d.locked or not d.qtime:
            self.game_timer.Stop()
            return
        left = max(0.0, d.deadline - time.monotonic())
        sec = int(left + 0.999)
        if self.o_timer_lbl:
            self.o_timer_lbl.SetLabel("Kalan süre: %d saniye" % sec)
        if self.o_gauge:
            self.o_gauge.SetValue(int(left / d.qtime * 1000))
        if 0 < sec <= 5 and sec != self.o_last_tick:
            self.o_last_tick = sec
            self.sounds.play("tick")
        if sec == 10 and not self.o_warned and d.qtime > 10:
            self.o_warned = True
            self.say("10 saniye kaldı.", interrupt=False)
        if left <= 0:
            self.lock_answer(-1)

    def online_pick(self, k):
        d = self.duel
        if d and d.phase == "q" and not d.locked:
            self.lock_answer(k)

    def lock_answer(self, k):
        d = self.duel
        if not d or d.phase != "q" or d.locked:
            return
        i = d.round
        full = d.qtime * 1000
        ms = full if k < 0 else min(full, int((time.monotonic() - d.q_start) * 1000))
        if not d.lock(k, ms):
            return
        self.game_timer.Stop()
        if self.sess:
            self.sess.send({"t": "ans", "i": i, "k": k, "ms": ms})
        q = d.qs[i]
        if k >= 0:
            self.opt_btns[k].SetLabel("%s: %s (seçildi)" % (LETTERS[k], q["o"][k]["t"]))
            self.sounds.play("joker")
        wait = "" if i in d.opp else " Rakip bekleniyor."
        text = ("Cevabın kilitlendi." if k >= 0 else "Süre doldu.") + wait
        if self.o_status_tc:
            self.o_status_tc.SetValue(text)
        self.say(("%s şıkkı kilitlendi." % LETTERS[k] if k >= 0 else "Süre doldu.") + wait)
        if i in d.opp:
            self.reveal_round(i)

    def reveal_round(self, i):
        d = self.duel
        if not d or not d.can_reveal(i):
            return
        d.phase = "reveal"
        self.sounds.play("kalp")
        self.later(1100, self.render_reveal, d, i)

    def render_reveal(self, d, i):
        if self.duel is not d or self.screen != "ogame":
            return
        res = d.resolve(i)
        q = d.qs[i]
        right, me, op = res["right"], res["me"], res["op"]
        if res["tie"] and self.is_host:
            ex = None
            used = {x["q"] for x in d.qs.values()}
            try:
                for _ in range(30):
                    ex = self.build_online_qs(1)[0]
                    if ex["q"] not in used:
                        break
                d.qs[i + 1] = ex
                self.sess.send({"t": "extra", "i": i + 1, "q": ex})
            except Exception:
                d.tie = False
                d.over = True
        for j, b in enumerate(self.opt_btns):
            tags = []
            if j == right:
                tags.append("doğru cevap")
            if j == me["k"]:
                tags.append("senin seçimin" if res["me_ok"] else "senin seçimin, yanlış")
            if j == op["k"]:
                tags.append("%s seçti" % self.opp_name)
            b.SetLabel("%s: %s%s" % (LETTERS[j], q["o"][j]["t"], " (%s)" % ", ".join(tags) if tags else ""))
        self.sounds.play("ok" if res["me_ok"] else "no")
        if self.o_players:
            self.o_players.SetLabel(self.players_text())
        if res["me_ok"]:
            me_msg = "Doğru! +%d puan." % res["me_p"]
        elif me["k"] < 0:
            me_msg = "Süre doldu. Doğru cevap %s: %s." % (LETTERS[right], q["o"][right]["t"])
        else:
            me_msg = "Yanlış. Doğru cevap %s: %s." % (LETTERS[right], q["o"][right]["t"])
        if op["k"] < 0:
            op_txt = "süre doldu"
        elif res["op_ok"]:
            op_txt = "doğru, +%d puan" % res["op_p"]
        else:
            op_txt = "yanlış"
        tail = "" if d.over else " Skor eşit, altın soru geliyor." if d.tie else ""
        label = "Sonucu gör" if d.over else "Altın soruya geç" if d.tie else "Hazırım"
        full = "%s %s: %s. %s%s" % (me_msg, self.opp_name, op_txt, q["e"], tail)

        lab = wx.StaticText(self.panel, label="Sonuç")
        lab.SetFont(self.font(11))
        self.fb_col.Add(lab, 0)
        tc = wx.TextCtrl(self.panel, value=full, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_WORDWRAP)
        tc.SetFont(self.font(15))
        tc.SetMinSize((-1, 90))
        tc.SetName("Sonuç")
        self.fb_col.Add(tc, 0, wx.EXPAND | wx.BOTTOM, 6)
        nb = wx.Button(self.panel, label=label)
        nb.SetFont(self.font(15, True))
        nb.SetMinSize((-1, 48))
        nb.SetDefault()
        self.fb_col.Add(nb, 0, wx.EXPAND | wx.BOTTOM, 6)
        nlab = wx.StaticText(self.panel, label="Bilgi")
        nlab.SetFont(self.font(11))
        self.fb_col.Add(nlab, 0)
        self.o_note_tc = wx.TextCtrl(self.panel, style=wx.TE_READONLY)
        self.o_note_tc.SetFont(self.font(13))
        self.o_note_tc.SetName("Bilgi")
        self.fb_col.Add(self.o_note_tc, 0, wx.EXPAND)
        self.finish_layout()
        tc.SetFocus()
        self.say("%s Puan: sen %d, %s %d.%s" % (
            me_msg + " " + self.opp_name + ": " + op_txt + ".", d.my_pts, self.opp_name, d.opp_pts, tail)
            + " " + q["e"])

        state = {"left": ol.O_REVEAL}

        def go_next():
            if self.duel is not d:
                return
            if d.over:
                self.end_online()
                return
            if d.my_ready.get(i + 1):
                return
            nb.Enable(False)
            self.o_note_tc.SetValue("Başlıyor…" if d.opp_ready.get(i + 1) else "Rakip bekleniyor…")
            self.o_note_tc.SetFocus()
            self.say(self.o_note_tc.GetValue())
            self.send_ready(i + 1)

        nb.Bind(wx.EVT_BUTTON, lambda e: self.go(go_next))
        if not d.over and not d.qtime:
            self.o_note_tc.SetValue("Hazır olduğunda düğmeye bas.")
        if not d.over and d.qtime:
            self.o_note_tc.SetValue("Sonraki soru %d saniye içinde başlar." % state["left"])

            def tick():
                if self.duel is not d or self.screen != "ogame" or d.my_ready.get(i + 1):
                    return
                state["left"] -= 1
                if state["left"] <= 0:
                    go_next()
                    return
                if self.o_note_tc:
                    self.o_note_tc.SetValue(
                        ("Rakip hazır. " if d.opp_ready.get(i + 1) else "") +
                        "Sonraki soru %d saniye içinde başlar." % state["left"])
                self.later(1000, tick)

            self.later(1000, tick)
        self.try_advance()

    # ------------------------------------------------------------ sonuç, rövanş
    def end_online(self):
        d = self.duel
        if not d or d.finished:
            return
        d.finished = True
        self.game_timer.Stop()
        me, opp = d.my_pts, d.opp_pts
        win = "Kazandın!" if me > opp else "Kaybettin." if me < opp else "Berabere!"
        line = "%d doğru – %d doğru" % (d.my_cor, d.opp_cor)
        self.post_game = True
        self.my_rematch = self.opp_rematch = False
        self.screen = "oresult"
        self.new_screen("Online - sonuç")
        self.add_heading(win)
        self.add_readonly("Skor", "%s – %s\n%d – %d\nDoğru sayısı: %s" % (
            self.my_name, self.opp_name, me, opp, line), height=130, size=20, bold=True)
        self.o_rm_tc = self.add_readonly("Rövanş durumu", "Rakibinle sohbet etmeye devam edebilirsin (S tuşu).",
                                         height=60, size=14)
        self.o_rm_btn = self.add_button("Rövanş", lambda e: self.go(self.request_rematch), primary=True)
        self.add_button("Yeni rakip", lambda e: self.go(self.show_online_menu))
        self.add_button("Rakibi bildir (B)", lambda e: self.report_opponent())
        self.add_button("Ana menü", lambda e: self.go(self.show_home))
        self.finish_layout()
        if me > opp:
            self.sounds.play("win")
        self.q_ctrl = None
        self.o_rm_tc.SetFocus()
        self.say("%s Puan %d – %d. Doğru sayısı: %s. Sohbet açık." % (win, me, opp, line))
        if not self.in_match:
            self._set_rm_status("Rakip ayrıldı.")
            self.o_rm_btn.Enable(False)

    def _set_rm_status(self, text):
        if self.screen == "oresult" and self.o_rm_tc:
            self.o_rm_tc.SetValue(text)
        self.say(text, interrupt=False)

    def request_rematch(self):
        if self.my_rematch or not self.post_game:
            return
        if not self.in_match:
            self._set_rm_status("Rakip ayrıldı.")
            return
        self.my_rematch = True
        self.sess.send({"t": "rematch"})
        if not self.opp_rematch:
            self._set_rm_status("Rövanş isteği gönderildi. Rakip bekleniyor…")
        self.try_rematch()

    def try_rematch(self):
        if self.my_rematch and self.opp_rematch and self.post_game and self.in_match:
            self.my_rematch = self.opp_rematch = False
            self.post_game = False
            self.sounds.play("bulundu")
            if self.is_host:
                self.later(600, self.host_setup)
            else:
                self.guest_wait("%s oyunu ayarlıyor." % self.opp_name)

    def on_opp_left(self):
        self.sounds.play("ayril")
        if self.post_game and self.screen == "oresult":
            self._set_rm_status("%s ayrıldı." % self.opp_name)
            if self.o_rm_btn:
                self.o_rm_btn.Enable(False)
            return
        name = self.opp_name
        self.online_close()
        self.show_disconnect(name)

    def show_disconnect(self, name):
        self.screen = "odisc"
        self.new_screen("Online - rakip ayrıldı")
        self.add_heading("Rakip ayrıldı")
        tc = self.add_readonly("Bilgi", "%s bağlantıdan ayrıldı." % name, height=70, size=16)
        b = self.add_button("Yeni rakip bul", lambda e: self.go(self.show_online_menu), primary=True)
        self.add_button("Ana menü", lambda e: self.go(self.show_home))
        self.finish_layout()
        tc.SetFocus()
        self.say("%s bağlantıdan ayrıldı." % name)

    def confirm_leave_online(self):
        dlg = wx.MessageDialog(self, "Düellodan ayrılmak istiyor musun? Rakibin oyunu kazanmış sayılmaz, oyun biter.",
                               "Düellodan ayrıl", wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        dlg.SetYesNoLabels("Evet, ayrıl", "Hayır, devam et")
        self.say("Düellodan ayrılınsın mı? Evet ya da hayır.")
        res = dlg.ShowModal()
        dlg.Destroy()
        if res == wx.ID_YES:
            self.go(self.show_online_menu)
        elif self.q_ctrl and self.screen == "ogame":
            self.q_ctrl.SetFocus()
            self.say("Oyuna devam ediliyor.")

    # ------------------------------------------------------------ sohbet
    def chat_send(self):
        if not self.in_match:
            return
        dlg = wx.TextEntryDialog(self, "Rakibe göndereceğin mesajı yaz:", "Sohbet")
        try:
            dlg.SetMaxLength(240)
        except Exception:
            pass
        self.say("Sohbet mesajı yaz ve Enter'a bas.")
        ok = dlg.ShowModal() == wx.ID_OK
        text = dlg.GetValue().strip()
        dlg.Destroy()
        if ok and text and self.in_match:
            self.sess.send({"t": "chat", "name": self.my_name, "text": text})
            self.chat.append("Sen: %s" % text)
            self.sounds.play("mesaj_gonder")
            self.say("Mesaj gönderildi.")
        if self.screen == "ogame" and self.q_ctrl:
            self.q_ctrl.SetFocus()

    def chat_read(self):
        if not self.chat:
            self.say("Henüz sohbet mesajı yok.")
        else:
            self.say("Son mesajlar. " + " ".join(self.chat[-5:]))

    # ------------------------------------------------------------ klavye yardımcıları
    def online_key(self, code, ch):
        """Online oyun ekranındaki tuşlar. İşlendiyse True döner."""
        if self.screen == "ogame" and self.duel:
            digit = None
            if ord("1") <= code <= ord("4"):
                digit = code - ord("1")
            elif wx.WXK_NUMPAD1 <= code <= wx.WXK_NUMPAD4:
                digit = code - wx.WXK_NUMPAD1
            if digit is not None:
                self.online_pick(digit)
                return True
            if ch == "C":
                if self.q_ctrl:
                    self.q_ctrl.SetFocus()
                self.say(self.online_question_speech(with_time=bool(self.duel.qtime)))
                return True
            if ch == "T":
                self.say(self.online_time_text())
                return True
            if ch == "P":
                self.say(self.players_text() + ".")
                return True
        if self.screen in ONLINE_SCREENS and ch == "B":
            self.report_opponent()
            return True
        if self.screen in ONLINE_SCREENS and self.in_match:
            if ch == "S":
                self.chat_send()
                return True
            if ch == "H":
                self.chat_read()
                return True
        return False
