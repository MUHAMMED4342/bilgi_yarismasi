# -*- coding: utf-8 -*-
"""
Çevrimiçi düello çekirdeği (arayüzden bağımsız).

Taşıyıcı: herkese açık MQTT sunucuları (paho-mqtt). Kendi sunucu gerekmez.
NOT: Web sürümü PeerJS/WebRTC kullanır; bu sürüm ayrı bir kanal kullandığı için
yalnızca bu Python uygulamasını kullananlarla eşleşir.
"""
import json
import random
import socket
import ssl
import struct
import threading
import traceback
import time
import uuid

PREFIX = "bilgiarena-py/v1"
LOBBY = PREFIX + "/lobby"
CH = PREFIX + "/ch/"

# (sunucu, port, taşıma, tls). Özel oda kodunun ilk hanesi bu listedeki sırayı taşır,
# böylece iki oyuncu da aynı sunucuya bağlanır.
BROKERS = [
    ("broker.emqx.io", 8883, "tcp", True),
    ("broker.hivemq.com", 8883, "tcp", True),
    ("broker.emqx.io", 1883, "tcp", False),
    ("broker.hivemq.com", 1883, "tcp", False),
    ("broker.emqx.io", 8084, "websockets", True),
    ("broker.hivemq.com", 8884, "websockets", True),
]

# Aynı sunucunun farklı portları aynı "aile"dir (web sürümü WebSocket, Python TLS/TCP kullanır).
FAMILY = {"broker.emqx.io": 0, "broker.hivemq.com": 1}

PING_EVERY = 3.0
LOST_AFTER = 15.0
SEEK_WAIT = 1.6
OFFER_REFRESH = 4.0
JOIN_WAIT_RANDOM = 6.0
JOIN_WAIT_ROOM = 8.0

# ---------------------------------------------------------------- oyun kuralları
O_ROUNDS = 10
O_BASE = 100
O_BONUS = 100
O_REVEAL = 12
O_TIMES = (0, 20, 30, 45)


def round_points(ok, ms, qtime):
    if not ok:
        return 0
    if not qtime:
        return O_BASE
    return O_BASE + int(O_BONUS * max(0.0, 1 - ms / (qtime * 1000.0)) + 0.5)


def valid_questions(qs):
    """Rakipten gelen soru listesini doğrular. Geçersizse None döner."""
    if not isinstance(qs, list) or not (1 <= len(qs) <= 30):
        return None
    out = []
    for q in qs:
        q = valid_question(q)
        if q is None:
            return None
        out.append(q)
    return out


def valid_question(q):
    try:
        opts = q["o"]
        if len(opts) != 4 or sum(1 for o in opts if o.get("c")) != 1:
            return None
        return {
            "cat": str(q.get("cat", ""))[:60],
            "q": str(q["q"])[:400],
            "o": [{"t": str(o["t"])[:200], "c": bool(o.get("c"))} for o in opts],
            "e": str(q.get("e", ""))[:400],
        }
    except Exception:
        return None


class Duel:
    """İki oyunculu eşzamanlı düellonun durumu (site mantığının birebir karşılığı)."""

    def __init__(self, qs, qtime):
        self.qs = {i: q for i, q in enumerate(qs)}
        self.qtime = qtime if qtime in O_TIMES else 20
        self.round = -1
        self.phase = "vs"
        self.locked = False
        self.my, self.opp = {}, {}
        self.my_pts = self.opp_pts = 0
        self.my_cor = self.opp_cor = 0
        self.hist = {}
        self.my_ready, self.opp_ready = {}, {}
        self.finished = False
        self.over = False
        self.tie = False
        self.q_start = 0.0
        self.deadline = 0.0
        self._resolved = {}

    def begin_round(self, n, now):
        self.round = n
        self.phase = "q"
        self.locked = False
        self.q_start = now
        self.deadline = now + self.qtime

    def lock(self, k, ms):
        if self.phase != "q" or self.locked:
            return False
        self.locked = True
        self.my[self.round] = {"k": k, "ms": ms}
        return True

    def opp_answer(self, i, k, ms):
        k = k if isinstance(k, int) and -1 <= k < 4 else -1
        try:
            ms = float(ms)
        except (TypeError, ValueError):
            ms = 0.0
        ms = min(self.qtime * 1000.0, max(0.0, ms))
        self.opp[i] = {"k": k, "ms": ms}

    def can_reveal(self, i):
        return self.phase == "q" and self.round == i and i in self.my and i in self.opp

    def can_advance(self):
        n = self.round + 1
        return (self.phase != "q" and bool(self.my_ready.get(n))
                and bool(self.opp_ready.get(n)) and n in self.qs)

    def resolve(self, i):
        if i in self._resolved:
            return self._resolved[i]
        q = self.qs[i]
        right = next(j for j, o in enumerate(q["o"]) if o["c"])
        me, op = self.my[i], self.opp[i]
        me_ok, op_ok = me["k"] == right, op["k"] == right
        me_p = round_points(me_ok, me["ms"], self.qtime)
        op_p = round_points(op_ok, op["ms"], self.qtime)
        self.my_pts += me_p
        self.opp_pts += op_p
        self.my_cor += 1 if me_ok else 0
        self.opp_cor += 1 if op_ok else 0
        self.hist[i] = {"ok": me_ok, "oppOk": op_ok}
        last = i >= O_ROUNDS - 1
        self.over = last and self.my_pts != self.opp_pts
        self.tie = last and self.my_pts == self.opp_pts
        res = {"right": right, "me": me, "op": op, "me_ok": me_ok, "op_ok": op_ok,
               "me_p": me_p, "op_p": op_p, "over": self.over, "tie": self.tie}
        self._resolved[i] = res
        return res


# ---------------------------------------------------------------- günlük
LOG_PATH = None


def log(msg):
    if not LOG_PATH:
        return
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


# ---------------------------------------------------------------- MQTT taşıyıcı
def _enc_len(n):
    out = bytearray()
    while True:
        b = n % 128
        n //= 128
        if n:
            b |= 0x80
        out.append(b)
        if not n:
            break
    return bytes(out)


def _mstr(s):
    b = s.encode("utf-8") if isinstance(s, str) else bytes(s)
    return struct.pack("!H", len(b)) + b


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("bağlantı kapandı")
        buf += chunk
    return buf


def _read_packet(sock):
    hdr = _recv_exact(sock, 1)[0]
    mult, length = 1, 0
    for _ in range(4):
        b = _recv_exact(sock, 1)[0]
        length += (b & 127) * mult
        mult *= 128
        if not b & 128:
            break
    return hdr, _recv_exact(sock, length) if length else b""


class LiteClient:
    """Ek paket gerektirmeyen küçük MQTT 3.1.1 istemcisi (TCP ve TLS)."""

    def __init__(self, host, port, tls, cid, will_topic, will_payload, on_message):
        self.host, self.port, self.tls, self.cid = host, port, tls, cid
        self.will_topic, self.will_payload = will_topic, will_payload
        self.on_message = on_message
        self.sock = None
        self.slock = threading.Lock()
        self.closing = False
        self.topics = set()
        self.pid = 0
        self.keepalive = 20

    def open(self, timeout):
        sock = socket.create_connection((self.host, self.port), timeout=timeout)
        try:
            if self.tls:
                ctx = ssl.create_default_context()
                sock = ctx.wrap_socket(sock, server_hostname=self.host)
            sock.settimeout(timeout)
            flags = 0x02
            payload = _mstr(self.cid)
            if self.will_topic:
                flags |= 0x04 | 0x08  # will, QoS 1
                payload += _mstr(self.will_topic) + _mstr(self.will_payload or b"")
            body = _mstr("MQTT") + bytes([4, flags]) + struct.pack("!H", self.keepalive) + payload
            sock.sendall(bytes([0x10]) + _enc_len(len(body)) + body)
            hdr, data = _read_packet(sock)
            if hdr >> 4 != 2 or len(data) < 2:
                raise ConnectionError("beklenmeyen yanıt")
            if data[1] != 0:
                raise ConnectionError("sunucu bağlantıyı reddetti (kod %d)" % data[1])
            sock.settimeout(None)
        except Exception:
            try:
                sock.close()
            except OSError:
                pass
            raise
        self.sock = sock

    def start(self):
        threading.Thread(target=self._reader, daemon=True).start()
        threading.Thread(target=self._pinger, daemon=True).start()

    def _send(self, data):
        with self.slock:
            s = self.sock
            if s is None:
                return False
            try:
                s.sendall(data)
                return True
            except OSError:
                return False

    def _next_pid(self):
        self.pid = self.pid % 65535 + 1
        return self.pid

    def subscribe(self, topic):
        self.topics.add(topic)
        self._send_sub(topic)

    def _send_sub(self, topic):
        body = struct.pack("!H", self._next_pid()) + _mstr(topic) + bytes([1])
        self._send(bytes([0x82]) + _enc_len(len(body)) + body)

    def unsubscribe(self, topic):
        self.topics.discard(topic)
        body = struct.pack("!H", self._next_pid()) + _mstr(topic)
        self._send(bytes([0xA2]) + _enc_len(len(body)) + body)

    def publish(self, topic, payload, retain=False):
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        body = _mstr(topic) + struct.pack("!H", self._next_pid()) + payload
        self._send(bytes([0x30 | 0x02 | (1 if retain else 0)]) + _enc_len(len(body)) + body)

    def _pinger(self):
        while not self.closing:
            time.sleep(10)
            if not self.closing:
                self._send(b"\xc0\x00")

    def _reader(self):
        while not self.closing:
            try:
                hdr, data = _read_packet(self.sock)
                self._handle(hdr, data)
            except Exception:
                if self.closing:
                    return
                self._reconnect()

    def _reconnect(self):
        with self.slock:
            try:
                if self.sock:
                    self.sock.close()
            except OSError:
                pass
            self.sock = None
        while not self.closing:
            time.sleep(2)
            try:
                self.open(6)
                for t in list(self.topics):
                    self._send_sub(t)
                log("yeniden bağlandı: %s" % self.host)
                return
            except Exception:
                continue

    def _handle(self, hdr, data):
        if hdr >> 4 != 3:
            return
        qos = (hdr >> 1) & 3
        retain = bool(hdr & 1)
        tlen = struct.unpack("!H", data[:2])[0]
        topic = data[2:2 + tlen].decode("utf-8", "replace")
        idx = 2 + tlen
        if qos:
            pid = data[idx:idx + 2]
            idx += 2
            if qos == 1:
                self._send(b"\x40\x02" + pid)
        self.on_message(topic, bytes(data[idx:]), retain)

    def close(self):
        self.closing = True
        self._send(b"\xe0\x00")
        with self.slock:
            s, self.sock = self.sock, None
        try:
            if s:
                s.close()
        except OSError:
            pass


class PahoBackend:
    """WebSocket sunucuları için (yalnızca paho-mqtt kuruluysa)."""

    def __init__(self, on_message):
        self.on_message = on_message
        self.client = None
        self.topics = set()
        self.lock = threading.Lock()

    def open(self, host, port, kind, tls, will_topic, will_payload, timeout):
        import paho.mqtt.client as mqtt
        cid = "by-" + uuid.uuid4().hex[:14]
        try:
            c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, client_id=cid, transport=kind)
        except (AttributeError, TypeError):
            c = mqtt.Client(client_id=cid, transport=kind)
        if tls:
            c.tls_set()
        if kind == "websockets":
            c.ws_set_options(path="/mqtt")
        if will_topic:
            c.will_set(will_topic, will_payload, qos=1)
        ev = threading.Event()

        def on_connect(cl, ud, flags, rc):
            if rc == 0:
                with self.lock:
                    ts = list(self.topics)
                for t in ts:
                    cl.subscribe(t, 1)
                ev.set()

        c.on_connect = on_connect
        c.on_message = lambda cl, ud, m: self.on_message(m.topic, bytes(m.payload), bool(m.retain))
        c.reconnect_delay_set(1, 8)
        c.connect_async(host, port, keepalive=20)
        c.loop_start()
        if not ev.wait(timeout):
            try:
                c.loop_stop()
                c.disconnect()
            except Exception:
                pass
            raise ConnectionError("zaman aşımı")
        self.client = c

    def subscribe(self, topic):
        with self.lock:
            self.topics.add(topic)
        self.client.subscribe(topic, 1)

    def unsubscribe(self, topic):
        with self.lock:
            self.topics.discard(topic)
        self.client.unsubscribe(topic)

    def publish(self, topic, payload, retain=False):
        self.client.publish(topic, payload, qos=1, retain=retain)

    def close(self):
        try:
            self.client.disconnect()
            self.client.loop_stop()
        except Exception:
            pass


class MqttTransport:
    def __init__(self, on_message):
        self.on_message = on_message
        self.b = None
        self.broker_index = None

    def connect(self, preferred=None, will_topic=None, will_payload=b"", per_try=4.0, progress=None):
        order = [i for i, b in enumerate(BROKERS) if preferred is not None and FAMILY.get(b[0]) == preferred]
        if not order:
            order = list(range(len(BROKERS)))
        reasons = []
        for n, idx in enumerate(order, 1):
            host, port, kind, tls = BROKERS[idx]
            if progress:
                progress(n, len(order))
            try:
                if kind == "websockets":
                    b = PahoBackend(self.on_message)
                    b.open(host, port, kind, tls, will_topic, will_payload, per_try)
                else:
                    b = LiteClient(host, port, tls, "by-" + uuid.uuid4().hex[:14],
                                   will_topic, will_payload, self.on_message)
                    b.open(per_try)
                    b.start()
                self.b = b
                self.broker_index = idx
                log("bağlandı: %s:%d (%s)" % (host, port, kind))
                return idx
            except ImportError:
                reasons.append("%s:%d websocket atlandı (paho-mqtt kurulu değil)" % (host, port))
            except Exception as e:  # noqa
                reasons.append("%s:%d %s: %s: %s" % (host, port, kind, type(e).__name__, e))
        for r in reasons:
            log("başarısız: " + r)
        err = ConnectionError("; ".join(reasons))
        err.reasons = reasons
        raise err

    def subscribe(self, topic):
        if self.b:
            self.b.subscribe(topic)

    def unsubscribe(self, topic):
        if self.b:
            self.b.unsubscribe(topic)

    def publish(self, topic, payload, retain=False):
        if self.b:
            self.b.publish(topic, payload, retain)

    def disconnect(self):
        b, self.b = self.b, None
        if b:
            b.close() if hasattr(b, "close") else None


# ---------------------------------------------------------------- oturum
class Session:
    """Eşleşme, el sıkışma, kalp atışı ve mesajlaşma.

    emit(olay, **veri) herhangi bir iş parçacığından çağrılabilir. Olaylar:
      status(text) | room_ready(code) | error(text) | matched(role, opp_name)
      msg(data)    | left()
    """

    def __init__(self, transport_factory, emit, name, pid="", banned=None):
        self.tf = transport_factory
        self.emit = emit
        self.name = (name or "Oyuncu")[:20]
        self.pid = pid or ""            # kalıcı oyuncu kimliği (yasak denetimi için)
        self.banned = banned if banned is not None else {}
        self.opp_pid = ""
        self.id = uuid.uuid4().hex[:10]
        self.lock = threading.RLock()
        self.tr = None
        self.state = "idle"  # idle seeking hosting joining matched closed
        self.random = False
        self.channel = None
        self.opp = None
        self.opp_name = "Rakip"
        self.is_host = False
        self.seq = 0
        self.seen = {}
        self.last_seen = 0.0
        self.next_ping = 0.0
        self.offer = None
        self.offer_ch = None
        self.seek_deadline = 0.0
        self.hello_deadline = 0.0
        self.next_offer = 0.0
        self.join_from_lobby = False
        self.left_sent = False
        self.closed = False
        self.broker = None

    # ----- dışarıya açık
    def start_random(self):
        self.random = True
        self._launch(self._boot_random)

    def host_room(self):
        self.random = False
        self._launch(self._boot_room)

    def join_room(self, code):
        self.random = False
        self._launch(lambda: self._boot_join(code))

    @property
    def matched(self):
        return self.state == "matched"

    def send(self, data):
        with self.lock:
            if self.state != "matched" or not self.channel:
                return False
            self._pub(self.channel, dict(data, to=self.opp))
            return True

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            prev = self.state
            tr = self.tr
            if tr:
                try:
                    if prev == "matched" and self.channel:
                        self._pub(self.channel, {"t": "bye", "to": self.opp})
                    if prev in ("hosting", "seeking") and self.random:
                        tr.publish(LOBBY, b"", retain=True)
                except Exception:
                    pass
            self.state = "closed"
        if tr:
            threading.Thread(target=self._shutdown, args=(tr,), daemon=True).start()

    def _shutdown(self, tr):
        time.sleep(0.4)  # son mesajların (bye) gitmesi için
        try:
            tr.disconnect()
        except Exception:
            pass

    # ----- içeride
    def _launch(self, fn):
        def run():
            try:
                fn()
            except ConnectionError as e:
                detail = str(e)
                reasons = getattr(e, "reasons", None)
                if reasons:
                    detail = reasons[-1]
                self._fail("Çevrimiçi sunucuya bağlanılamadı. İnternet bağlantını ve güvenlik duvarını kontrol et. "
                           "Ayrıntı: %s (kayıt: veri klasöründeki online_log.txt)" % detail[:140])
            except Exception as e:  # noqa
                log("beklenmeyen hata:\n" + traceback.format_exc())
                self._fail("Çevrimiçi mod başlatılamadı: %s: %s (kayıt: veri klasöründeki online_log.txt)"
                           % (type(e).__name__, str(e)[:140]))
        threading.Thread(target=run, daemon=True).start()

    def _fail(self, text):
        with self.lock:
            if self.closed:
                return
        self.emit("error", text=text)

    def _connect(self, preferred=None):
        self.emit("status", text="Sunucuya bağlanılıyor…")
        tr = self.tf(self._on_message)
        will = json.dumps({"t": "gone", "from": self.id}).encode()

        def progress(i, n):
            if n > 1:
                self.emit("status", text="Sunucuya bağlanılıyor (%d/%d)…" % (i, n))

        self.broker = tr.connect(preferred, PREFIX + "/presence/" + self.id, will, progress=progress)
        with self.lock:
            if self.closed:
                tr.disconnect()
                return False
            self.tr = tr
        threading.Thread(target=self._worker, daemon=True).start()
        return True

    def _boot_random(self):
        if not self._connect():
            return
        with self.lock:
            self.state = "seeking"
            self.seek_deadline = time.monotonic() + SEEK_WAIT
            self.tr.subscribe(LOBBY)
        self.emit("status", text="Rakip aranıyor… Havuzda bekleyen biri varsa eşleşeceksiniz.")

    def _boot_room(self):
        if not self._connect():
            return
        with self.lock:
            fam = FAMILY.get(BROKERS[self.broker][0], 9) if self.broker is not None and self.broker < len(BROKERS) else 9
            code = "%d%05d" % (fam, random.randint(0, 99999))
            self.channel = CH + "room-" + code
            self.state = "hosting"
            self.is_host = True
            self.tr.subscribe(self.channel)
        self.emit("room_ready", code=code)

    def _boot_join(self, code):
        code = (code or "").strip()
        pref = int(code[0]) if code[:1].isdigit() else None
        if not self._connect(pref):
            return
        with self.lock:
            self.channel = CH + "room-" + code
            self.join_from_lobby = False
            self.tr.subscribe(self.channel)
            self._start_joining(None, JOIN_WAIT_ROOM)
        self.emit("status", text="Odaya bağlanılıyor…")

    def _start_joining(self, host_id, wait):
        self.state = "joining"
        self.hello_deadline = time.monotonic() + wait
        self._pub(self.channel, {"t": "join", "name": self.name, "pid": self.pid, "to": host_id})

    def _pub(self, topic, d, retain=False):
        d = dict(d)
        d["from"] = self.id
        d["n"] = self.seq
        self.seq += 1
        self.tr.publish(topic, json.dumps(d, ensure_ascii=False).encode("utf-8"), retain=retain)

    # ----- gelen mesajlar
    def _on_message(self, topic, payload, retained=False):
        if not payload:
            return
        try:
            d = json.loads(payload.decode("utf-8"))
            if not isinstance(d, dict):
                return
        except Exception:
            return
        with self.lock:
            if self.closed:
                return
            if topic == LOBBY:
                self._on_lobby(d)
            elif topic.startswith(PREFIX + "/presence/"):
                if self.state == "matched" and topic.endswith("/" + str(self.opp)):
                    self._opp_left()
            elif topic == self.channel:
                self._on_channel(d)

    def _on_lobby(self, d):
        if d.get("t") != "wait" or d.get("id") == self.id:
            return
        if not isinstance(d.get("ch"), str) or not isinstance(d.get("id"), str) \
                or not d["ch"].startswith(CH):
            return
        if self._is_banned(d.get("pid")):
            return
        if self.state == "seeking":
            self.offer = d
        elif self.state == "hosting" and self.random and d["id"] < self.id:
            # İki kişi aynı anda bekleyici olduysa kimliği büyük olan diğerine katılır.
            self._switch_to(d)

    def _is_banned(self, pid):
        return isinstance(pid, str) and bool(pid) and pid in self.banned

    @staticmethod
    def _clean_pid(pid):
        return pid if isinstance(pid, str) and len(pid) == 16 and all(c in "0123456789abcdef" for c in pid) else ""

    def _switch_to(self, offer):
        old = self.channel
        self.channel = offer["ch"]
        self.is_host = False
        self.join_from_lobby = True
        self.tr.subscribe(self.channel)
        if old and old != self.channel:
            self.tr.unsubscribe(old)
        self._start_joining(offer["id"], JOIN_WAIT_RANDOM)
        self.emit("status", text="Rakip bulundu, bağlanılıyor…")

    def _become_host_random(self):
        self.channel = CH + "rnd-" + self.id
        self.is_host = True
        self.state = "hosting"
        self.tr.subscribe(self.channel)
        self._publish_offer()
        self.emit("status", text="Rakip aranıyor… Biri katılınca oyun başlayacak.")

    def _publish_offer(self):
        self.next_offer = time.monotonic() + OFFER_REFRESH
        self._pub(LOBBY, {"t": "wait", "id": self.id, "ch": self.channel, "name": self.name, "pid": self.pid}, retain=True)

    def _on_channel(self, d):
        sender = d.get("from")
        if not isinstance(sender, str) or sender == self.id:
            return
        n = d.get("n")
        if isinstance(n, int):
            seen = self.seen.setdefault(sender, [])
            if n in seen:
                return
            seen.append(n)
            del seen[:-300]
        t = d.get("t")
        if self.state == "hosting" and t == "join":
            if not self._is_banned(d.get("pid")):
                self._accept_guest(sender, d)
        elif self.state == "joining" and t == "hello" and d.get("to") == self.id:
            if self._is_banned(d.get("pid")):
                self.state = "closed"
                self.emit("error", text="Bu oyuncu yasaklı olduğu için eşleşme iptal edildi.")
            else:
                self._accept_host(sender, d)
        elif self.state == "joining" and t == "full" and d.get("to") == self.id:
            self.state = "closed"
            self.emit("error", text="Oda dolu.")
        elif self.state == "matched":
            if t == "join" and sender != self.opp:
                self._pub(self.channel, {"t": "full", "to": sender})
            elif sender == self.opp:
                self.last_seen = time.monotonic()
                if t == "bye":
                    self._opp_left()
                elif t == "ping":
                    pass
                elif t == "join":  # hello kaybolduysa yeniden gönder
                    self._pub(self.channel, {"t": "hello", "to": sender, "name": self.name, "pid": self.pid})
                elif d.get("to") in (None, self.id):
                    self.emit("msg", data=d)

    def _accept_guest(self, sender, d):
        target = d.get("to")
        if target not in (None, self.id):
            return
        self.opp = sender
        self.opp_name = str(d.get("name") or "Rakip")[:20]
        self.opp_pid = self._clean_pid(d.get("pid"))
        self._pub(self.channel, {"t": "hello", "to": sender, "name": self.name, "pid": self.pid})
        if self.random:
            self.tr.publish(LOBBY, b"", retain=True)
            self.tr.unsubscribe(LOBBY)
        self._matched("host")

    def _accept_host(self, sender, d):
        self.opp = sender
        self.opp_name = str(d.get("name") or "Rakip")[:20]
        self.opp_pid = self._clean_pid(d.get("pid"))
        if self.join_from_lobby:
            self.tr.unsubscribe(LOBBY)
        self._matched("guest")

    def _matched(self, role):
        self.state = "matched"
        self.is_host = role == "host"
        self.last_seen = time.monotonic()
        self.next_ping = self.last_seen + PING_EVERY
        self.tr.subscribe(PREFIX + "/presence/" + self.opp)
        self.emit("matched", role=role, opp_name=self.opp_name, opp_pid=self.opp_pid)

    def _opp_left(self):
        if self.left_sent:
            return
        self.left_sent = True
        self.emit("left")

    # ----- zamanlayıcı iş parçacığı
    def _worker(self):
        while True:
            time.sleep(0.25)
            with self.lock:
                if self.closed:
                    return
                now = time.monotonic()
                st = self.state
                try:
                    if st == "seeking" and now >= self.seek_deadline:
                        if self.offer:
                            offer, self.offer = self.offer, None
                            self.join_from_lobby = True
                            self.channel = offer["ch"]
                            self.is_host = False
                            self.tr.subscribe(self.channel)
                            self._start_joining(offer["id"], JOIN_WAIT_RANDOM)
                            self.emit("status", text="Rakip bulundu, bağlanılıyor…")
                        else:
                            self._become_host_random()
                    elif st == "hosting" and self.random and now >= self.next_offer:
                        self._publish_offer()
                    elif st == "joining" and now >= self.hello_deadline:
                        if self.join_from_lobby:
                            # Bayat ilan: temizle ve kendimiz bekleyici olalım.
                            self.tr.publish(LOBBY, b"", retain=True)
                            old = self.channel
                            self.join_from_lobby = False
                            self._become_host_random()
                            if old and old != self.channel:
                                self.tr.unsubscribe(old)
                        else:
                            self.state = "closed"
                            self.emit("error", text="Oda bulunamadı veya kod yanlış.")
                    elif st == "matched":
                        if now >= self.next_ping:
                            self.next_ping = now + PING_EVERY
                            self._pub(self.channel, {"t": "ping", "to": self.opp})
                        if now - self.last_seen > LOST_AFTER:
                            self._opp_left()
                except Exception:
                    pass
