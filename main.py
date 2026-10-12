import random
import sys
import time
import os
import re
import numpy as np
import io

# Tắt TensorFlow warnings và logs
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

import warnings
warnings.filterwarnings("ignore")

def suppress_tensorflow_logs():
    """Tắt các log và warning của TensorFlow"""
    try:
        import tensorflow as tf
        tf.get_logger().setLevel('ERROR')
        tf.autograph.set_verbosity(0)
    except ImportError:
        pass

# ============================================================
# STATUS UI — Clean Minimalist Typography (ANSI thuần, không box Unicode)
# - Căn chỉnh bằng spaces + ljust, không dùng rich/curses
# - Anti-flicker: gom 1 string, xuất 1 lần bằng \033[H\033[J
# - An toàn: try/except + getattr fallback, không crash vòng lặp chính
# ============================================================
try:
    import colorama
    colorama.init()
except ImportError:
    os.system("")  # bật mã ANSI cho console Windows 10+

CLR_TITLE = "\033[1;97m"    # Bold White — tiêu đề và giá trị chính
CLR_LABEL = "\033[1;96m"    # Cyan — label danh mục
CLR_SUCCESS = "\033[1;92m"  # Green — thành công / số tạo được
CLR_WARN = "\033[1;93m"     # Yellow — cảnh báo / target đang soi
CLR_ERROR = "\033[1;91m"    # Red — lỗi
CLR_DIM = "\033[90m"        # Dim Gray — text phụ / phân cách
CLR_RESET = "\033[0m"

# Giữ map màu cũ để hàm log(tag) cũ vẫn tương thích khi chuyển sang activity
_TAG_TO_LEVEL = {
    "OK": ">",
    "SAVE": ">",
    "INFO": "-",
    "WARN": "*",
    "ERROR": "!",
    "CAPTCHA": "*",
}

DIVIDER = "-" * 72
MAX_LOG_LEN = 90


class GenState:
    """State dùng chung cho print_status. Field names giữ đúng spec để tái dùng."""
    def __init__(self):
        self.app_name = "WEBSHARE GEN"
        self.version = "v2.2.0"
        self.status = "STARTING"
        self.mode = "UC Headed | Retry5 Capt300s"
        self.account_name = "---"
        self.account_id = "0"
        self.bought_count = 0      # tổng acc tạo thành công
        self.target_item = "Idle"  # stage hiện tại + email
        self.queue_items = []
        self.queue_total = 0
        self.searches_count = 0    # giữ để tương thích cũ, không còn hiển thị
        self.loop_v1 = 0.0         # thời gian REGISTER acc gần nhất
        self.loop_v2 = 0.0         # thời gian PROXY+KEY acc gần nhất
        self.threads_count = 1     # giữ để tương thích cũ, không còn hiển thị
        self.max_price = "Retry 5 | Capt 300s"  # giữ để tương thích cũ, đã gộp vào MODE
        self.proxy_active = True
        self.alive_proxies = 0     # tổng proxy đã cào
        self.webhook_active = False  # tái dùng làm cờ API Key acc gần nhất OK?
        self.fail_count = 0        # số acc lỗi liên tiếp, dừng ở 3
        self.recent_logs = []      # list (level, text), giữ tối đa 12, hiện 4


STATE = GenState()


def push_activity(level, text):
    """Đẩy 1 dòng vào timeline, giữ tối đa 12 dòng mới nhất."""
    try:
        lv = str(level) if level else "-"
        msg = str(text) if text is not None else ""
        logs = getattr(STATE, "recent_logs", None)
        if not isinstance(logs, list):
            STATE.recent_logs = []
            logs = STATE.recent_logs
        logs.append((lv, msg))
        if len(logs) > 12:
            del logs[0:len(logs) - 12]
    except Exception:
        pass


def print_status(s) -> None:
    """Render dashboard 4 khối. Luôn an toàn, không bao giờ raise."""
    try:
        app_name = str(getattr(s, "app_name", "WEBSHARE GEN")).strip()
        version = str(getattr(s, "version", "")).strip()
        status_text = str(getattr(s, "status", "IDLE")).strip().upper()
        mode_text = str(getattr(s, "mode", "")).strip()

        account_name = str(getattr(s, "account_name", "---")).strip()
        account_id = str(getattr(s, "account_id", "0")).strip()
        try:
            bought_count = int(getattr(s, "bought_count", 0))
        except Exception:
            bought_count = 0

        target_item = str(getattr(s, "target_item", "Idle")).strip()
        queue_items = getattr(s, "queue_items", [])
        if not isinstance(queue_items, (list, tuple)):
            queue_items = []
        try:
            queue_total = int(getattr(s, "queue_total", len(queue_items)))
        except Exception:
            queue_total = len(queue_items)

        try:
            loop_v1 = float(getattr(s, "loop_v1", 0.0))
        except Exception:
            loop_v1 = 0.0
        try:
            loop_v2 = float(getattr(s, "loop_v2", 0.0))
        except Exception:
            loop_v2 = 0.0
        try:
            proxy_status = bool(getattr(s, "proxy_active", False))
        except Exception:
            proxy_status = False
        try:
            alive_proxies = int(getattr(s, "alive_proxies", 0))
        except Exception:
            alive_proxies = 0
        try:
            key_ok = bool(getattr(s, "webhook_active", False))
        except Exception:
            key_ok = False
        try:
            fail_count = int(getattr(s, "fail_count", 0))
        except Exception:
            fail_count = 0

        recent_logs = getattr(s, "recent_logs", [])
        if not isinstance(recent_logs, (list, tuple)):
            recent_logs = []

        if status_text in ("ACTIVE", "RUNNING", "REGISTERING", "FETCHING PROXY", "FETCHING KEY"):
            status_color = CLR_SUCCESS
        elif status_text in ("STARTING", "WAITING CAPTCHA", "RETRY EMAIL", "IDLE"):
            status_color = CLR_WARN
        else:
            status_color = CLR_ERROR

        preview = ", ".join(str(x) for x in list(queue_items)[:4])
        queue_preview = preview if preview else "empty"

        if proxy_status:
            proxy_txt = CLR_TITLE + str(alive_proxies) + CLR_RESET
        else:
            proxy_txt = CLR_ERROR + "OFF" + CLR_RESET
        if key_ok:
            key_txt = CLR_SUCCESS + "ON" + CLR_RESET
        else:
            key_txt = CLR_DIM + "OFF" + CLR_RESET
        if fail_count >= 3:
            fail_txt = CLR_ERROR + str(fail_count) + CLR_RESET
        elif fail_count >= 1:
            fail_txt = CLR_WARN + str(fail_count) + CLR_RESET
        else:
            fail_txt = CLR_SUCCESS + "0" + CLR_RESET

        lines = []
        lines.append(
            CLR_TITLE + app_name + CLR_RESET
            + " " + CLR_DIM + version + CLR_RESET
            + "   " + CLR_DIM + "STATUS" + CLR_RESET + " " + status_color + status_text + CLR_RESET
            + "   " + CLR_DIM + "MODE" + CLR_RESET + " " + CLR_TITLE + mode_text + CLR_RESET
        )
        lines.append(CLR_DIM + DIVIDER + CLR_RESET)
        lines.append(
            CLR_LABEL + "ACCOUNT".ljust(10) + CLR_RESET
            + CLR_TITLE + account_name + CLR_RESET
            + " " + CLR_DIM + "#" + account_id + CLR_RESET
            + "   " + CLR_LABEL + "DONE".ljust(6) + CLR_RESET
            + CLR_SUCCESS + str(bought_count) + CLR_RESET
        )
        lines.append(
            CLR_LABEL + "STAGE".ljust(10) + CLR_RESET
            + CLR_WARN + target_item + CLR_RESET
        )
        lines.append(
            CLR_LABEL + "QUEUE".ljust(10) + CLR_RESET
            + CLR_TITLE + str(queue_total) + CLR_RESET
            + " " + CLR_DIM + "(" + queue_preview + ")" + CLR_RESET
        )
        lines.append("")
        lines.append(
            CLR_LABEL + "LOOP".ljust(10) + CLR_RESET
            + "REG " + CLR_TITLE + f"{loop_v1:.1f}s" + CLR_RESET
            + " " + CLR_DIM + "|" + CLR_RESET + " "
            + "DATA " + CLR_TITLE + f"{loop_v2:.1f}s" + CLR_RESET
            + "   " + CLR_LABEL + "NET".ljust(5) + CLR_RESET
            + "Proxy " + proxy_txt
            + " " + CLR_DIM + "|" + CLR_RESET + " "
            + "Key " + key_txt
            + "   " + CLR_LABEL + "FAIL".ljust(6) + CLR_RESET
            + fail_txt
        )
        lines.append(CLR_DIM + DIVIDER + CLR_RESET)
        lines.append(CLR_LABEL + "RECENT ACTIVITY" + CLR_RESET)
        tail = list(recent_logs)[-4:] if recent_logs else []
        if not tail:
            lines.append("  " + CLR_DIM + "- No recent activities recorded." + CLR_RESET)
        else:
            for item in tail:
                lv = "-"
                msg = ""
                try:
                    if isinstance(item, (tuple, list)) and len(item) >= 2:
                        lv = str(item[0]).strip()
                        msg = str(item[1]).strip()
                    elif isinstance(item, dict):
                        lv = str(item.get("level", "-")).strip()
                        msg = str(item.get("msg", "")).strip()
                    else:
                        msg = str(item).strip()
                except Exception:
                    continue
                if len(msg) > MAX_LOG_LEN:
                    msg = msg[:MAX_LOG_LEN - 3] + "..."
                if lv in (">", "OK", "SAVE", "SUCCESS"):
                    tag = CLR_SUCCESS + ">" + CLR_RESET
                elif lv in ("!", "ERROR", "FAIL"):
                    tag = CLR_ERROR + "!" + CLR_RESET
                elif lv in ("*", "WARN", "CAPTCHA", "HOT"):
                    tag = CLR_WARN + "*" + CLR_RESET
                else:
                    tag = CLR_DIM + "-" + CLR_RESET
                lines.append("  " + tag + " " + msg)
        lines.append("")
        lines.append(CLR_DIM + "[Ctrl+C to stop]" + CLR_RESET)

        output = "\n".join(lines)
        sys.stdout.write("\033[H\033[J" + output + "\n")
        sys.stdout.flush()
    except Exception:
        pass


def render():
    """Shortcut render STATE hiện tại, không bao giờ crash."""
    try:
        print_status(STATE)
    except Exception:
        pass


def bump_searches(n=1):
    try:
        STATE.searches_count = int(getattr(STATE, "searches_count", 0)) + n
    except Exception:
        pass


def set_status(text):
    try:
        STATE.status = str(text)
    except Exception:
        pass


def set_stage(text):
    try:
        STATE.target_item = str(text)
    except Exception:
        pass


def log(tag, message="", indent=0):
    """API cũ giữ nguyên chữ ký — giờ đẩy vào timeline + render status."""
    try:
        msg = str(message) if message is not None else ""
        if indent:
            msg = " " * int(indent) + msg
        level = _TAG_TO_LEVEL.get(str(tag), "-") if tag else "-"
        if tag:
            push_activity(level, msg)
        elif msg:
            push_activity("-", msg)
        bump_searches(0)
        render()
    except Exception:
        pass


def banner(title):
    try:
        push_activity("-", str(title))
        render()
    except Exception:
        pass


def countdown(seconds, message):
    """Đếm ngược nhưng render vào status để chống giật, không print nhiều dòng."""
    try:
        for i in range(int(seconds), 0, -1):
            try:
                set_status("IDLE")
                set_stage(str(message) + " " + str(i) + "s")
                render()
            except Exception:
                pass
            time.sleep(1)
        try:
            set_stage("Starting next account")
            render()
        except Exception:
            pass
    except Exception:
        try:
            time.sleep(int(seconds))
        except Exception:
            pass

def short_error(e):
    """Rút gọn message lỗi selenium (bỏ stacktrace dài dòng)"""
    msg = str(e).strip().splitlines()[0]
    return msg[:160]

# ============================================================
# ĐƯỜNG DẪN (anchor theo vị trí script) & URL
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
ACCOUNTS_FILE = os.path.join(OUTPUT_DIR, "accounts.txt")
PROXIES_FILE = os.path.join(OUTPUT_DIR, "proxies.txt")
ACCOUNTS_DISPLAY = "output/accounts.txt"
PROXIES_DISPLAY = "output/proxies.txt"
os.makedirs(OUTPUT_DIR, exist_ok=True)

NAMES_FILE = os.path.join(BASE_DIR, "names.txt")
NAMES_DISPLAY = "names.txt"

REGISTER_URL = "https://proxy2.webshare.io/register"
PROXY_LIST_URL = "https://dashboard.webshare.io/proxy/list"
API_KEYS_URL = "https://dashboard.webshare.io/userapi/keys"
CAPTCHA_TIMEOUT_SECONDS = 300  # chờ người dùng giải captcha tối đa 5 phút
MAX_EMAIL_RETRIES = 5  # số mail khác nhau thử tối đa khi bị từ chối
EMAIL_ERROR_TEXTS = [
    "this email cannot be used",
    "try a different email",
    "already registered",
    "already in use",
    "invalid email",
]
EMAIL_CHECK_SECONDS = 10  # chờ lỗi email hiện ra sau mỗi lần click Sign Up

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import InvalidSessionIdException

sb = None          # SeleniumBase driver (khởi tạo trong main)
wait = None
names_list = []

class AccountFlowError(Exception):
    """Lỗi khiến account hiện tại thất bại → bỏ qua, chuyển acc tiếp theo"""

# ============================================================
# HELPERS
# ============================================================
def retry_step(step_name, func, max_attempts=3, wait_seconds=3):
    """Retry một bước, chỉ log khi có lỗi"""
    for attempt in range(1, max_attempts + 1):
        try:
            bump_searches(1)
            return func()
        except Exception as e:
            log("WARN", f"{step_name} — lần {attempt} lỗi: {short_error(e)}")
            if attempt < max_attempts:
                time.sleep(wait_seconds)
            else:
                log("ERROR", f"{step_name} thất bại sau {max_attempts} lần thử")
                return None

def generate_password():
    alphabets = 'abcdefghijklmnopqrstuvwxyz'
    digits = '0123456789'
    special_characters = '!@#&'

    password = random.choice(alphabets).upper() + ''.join(random.choice(alphabets + digits + special_characters) for _ in range(7))
    return password

def generate_emails(names=[]):
    email_list = []
    for nm in names:
        email_list.append(
            nm.strip().split('\n')[0] + '{}{}'.format(np.random.randint(1, 99), '@gmail.com')
        )
    return email_list

def _generate_single_email(exclude=None):
    """Sinh 1 email chưa dùng. Fallback thêm suffix timestamp để chắc chắn unique."""
    exclude = exclude or set()
    base = ""
    for _ in range(20):
        if not names_list:
            break
        base = random.choice(names_list).strip().split('\n')[0].strip()
        if not base:
            continue
        email = f"{base}{random.randint(1, 99)}@gmail.com"
        if email not in exclude:
            return email
    base = base or "user"
    return f"{base}{random.randint(100, 9999)}{int(time.time()) % 10000}@gmail.com"

EMAIL_SELECTORS = [
    "input[data-testid='email-input']",
    "input[type='email']",
    "input[name='email']",
    "#email-input",
]

def _fill_email_field(email):
    """Điền email vào form, thử nhiều selector. Trả về True/False."""
    for selector in EMAIL_SELECTORS:
        try:
            field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            field.clear()
            field.send_keys(email)
            return True
        except Exception:
            continue
    return False

def _click_signup():
    signup_selectors = [
        (By.CSS_SELECTOR, "button[data-testid*='signup']"),
        (By.CSS_SELECTOR, "button[type='submit']"),
        (By.XPATH, "//button[contains(text(), 'SIGN UP')]"),
        (By.XPATH, "//button[contains(text(), 'Sign Up')]"),
    ]
    for selector_type, selector_value in signup_selectors:
        try:
            btn = sb.find_element(selector_type, selector_value)
            if btn.is_displayed():
                btn.click()
                return True
        except Exception:
            continue
    raise Exception("Could not find sign up button!")

def _tick_terms_checkbox():
    """Tick checkbox Terms nếu chưa tick. Không raise — chỉ log WARN."""
    checkbox_selectors = [
        "input[type='checkbox'].PrivateSwitchBase-input",
        "input.PrivateSwitchBase-input",
        "input[type='checkbox']",
    ]
    try:
        time.sleep(1)
        for selector in checkbox_selectors:
            try:
                checkbox = sb.find_element(By.CSS_SELECTOR, selector)
                if not checkbox.is_selected():
                    parent = checkbox.find_element(By.XPATH, "..")
                    parent.click()
                    time.sleep(1)
                    return True
            except Exception:
                continue
        log("WARN", "Không thấy checkbox Terms — vẫn tiếp tục")
    except Exception as e:
        log("WARN", f"Lỗi tick checkbox: {e} — vẫn tiếp tục")
    return False

GO_TO_PROXY_LIST_XPATH = (
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    "'abcdefghijklmnopqrstuvwxyz'), 'go to proxy list')]"
)

GO_TO_PROXY_LIST_CSS = [
    "button[data-testid*='go-to-proxy']",
    "button[data-testid*='goto-proxy']",
    "button[data-testid*='proxy-list']",
]


def _any_displayed(els):
    try:
        for el in els or []:
            try:
                if el.is_displayed():
                    return True
            except Exception:
                continue
    except Exception:
        pass
    return False


def _go_to_proxy_list_visible(driver=None):
    """Nút 'Go To Proxy List' có đang hiển thị ở BẤT KỲ đâu? Chỉ dùng kèm
    điều kiện form đã ẩn (tránh nhầm link nav của trang register)."""
    drv = driver or sb
    try:
        if _any_displayed(drv.find_elements(By.XPATH, GO_TO_PROXY_LIST_XPATH)):
            return True
    except Exception:
        pass
    for selector in GO_TO_PROXY_LIST_CSS:
        try:
            if _any_displayed(drv.find_elements(By.CSS_SELECTOR, selector)):
                return True
        except Exception:
            continue
    return False


DIALOG_CONTAINER_XPATH = (
    "//*[contains(@role, 'dialog') or contains(@role, 'alertdialog') "
    "or contains(@class, 'Modal') or contains(@class, 'modal') "
    "or contains(@class, 'Dialog') or contains(@class, 'dialog') "
    "or contains(@class, 'popup') or contains(@class, 'Popup')]"
)

_DIALOG_CSS_PREFIXES = [
    "div[role='dialog']",
    "div[role='alertdialog']",
    ".MuiDialog-root",
    ".MuiModal-root",
]


def _go_to_proxy_list_in_dialog(driver=None):
    """Nút 'Go To Proxy List' nằm TRONG popup/modal success — bằng chứng chắc
    chắn 100% server đã chấp thuận tài khoản (không nhầm link nav)."""
    drv = driver or sb
    try:
        if _any_displayed(drv.find_elements(
                By.XPATH, DIALOG_CONTAINER_XPATH + GO_TO_PROXY_LIST_XPATH)):
            return True
    except Exception:
        pass
    for prefix in _DIALOG_CSS_PREFIXES:
        for selector in GO_TO_PROXY_LIST_CSS:
            try:
                if _any_displayed(drv.find_elements(
                        By.CSS_SELECTOR, prefix + " " + selector)):
                    return True
            except Exception:
                continue
    return False


def _register_form_visible():
    """Ô email form register còn hiển thị? Còn hiển thị = TUYỆT ĐỐI chưa xong."""
    try:
        for selector in EMAIL_SELECTORS:
            try:
                for el in sb.find_elements(By.CSS_SELECTOR, selector):
                    try:
                        if el.is_displayed():
                            return True
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception:
        pass
    return False


def _current_url_lower():
    try:
        return (sb.current_url or "").lower()
    except Exception:
        return ""


def _check_registration_success(settle_until=None):
    """Đã đăng ký thành công? Trả về (ok, reason).

    QUY TẮC BẤT DI BẤT DỊCH:
    - Kill-switch: còn đứng ở form register (URL chứa 'register' + ô email
      còn hiển thị) thì TUYỆT ĐỐI False, bất kể nút nào khớp.
    - Chỉ True khi: nút nằm trong popup success (btn-in-dialog), hoặc nút
      toàn trang kèm form đã ẩn (btn+form-gone), hoặc đã sang hẳn
      dashboard/proxy-list (dashboard-url = đã có session).
    - Trong settle sau click: chỉ soi lỗi mail, bỏ qua mọi tín hiệu SUCCESS.
    """
    try:
        try:
            settling = settle_until is not None and time.time() < settle_until
        except Exception:
            settling = False
        if settling:
            return False, ""
        try:
            url = _current_url_lower()
        except Exception:
            url = ""
        if "register" in (url or "") and _register_form_visible():
            return False, ""
        if _go_to_proxy_list_in_dialog():
            return True, "btn-in-dialog"
        if _go_to_proxy_list_visible() and not _register_form_visible():
            return True, "btn+form-gone"
        if url and ("dashboard.webshare.io" in url or "proxy/list" in url):
            return True, "dashboard-url"
        return False, ""
    except Exception:
        return False, ""


def _is_register_success():
    """Wrapper tương thích cũ."""
    try:
        ok, _ = _check_registration_success()
        return ok
    except Exception:
        return False


def _verify_account_created():
    """Cổng xác minh độc lập trước khi chuyển trang fetch proxy."""
    try:
        ok, reason = _check_registration_success()
        if ok:
            push_activity(">", f"Verify acc OK ({reason}) — chuyen sang fetch proxy")
            render()
            return True
        return False
    except Exception:
        return False


EMAIL_ERROR_XPATHS = [
    "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    "'abcdefghijklmnopqrstuvwxyz'), 'this email cannot be used')]",
    "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    "'abcdefghijklmnopqrstuvwxyz'), 'try a different email')]",
    "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    "'abcdefghijklmnopqrstuvwxyz'), 'already registered')]",
    "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    "'abcdefghijklmnopqrstuvwxyz'), 'email is already in use')]",
    "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    "'abcdefghijklmnopqrstuvwxyz'), 'email already in use')]",
]

EMAIL_ERROR_CSS = [
    "p.Mui-error",
    ".MuiFormHelperText-root.Mui-error",
    "[data-testid='email-error']",
]


def _check_email_rejected():
    """Chi nhan loi mail khi element DO dang hien thi. Tra ve text loi hoac None.

    Khong soi page_source de tranh bao nham text an trong JS.
    """
    try:
        # 1) O nhan loi chuan MUI gan o email
        for selector in EMAIL_ERROR_CSS:
            try:
                for el in sb.find_elements(By.CSS_SELECTOR, selector):
                    try:
                        if not el.is_displayed():
                            continue
                        text = (el.text or "").strip()
                        if not text:
                            continue
                        low = text.lower()
                        if any(p in low for p in EMAIL_ERROR_TEXTS):
                            return text[:160]
                    except Exception:
                        continue
            except Exception:
                continue
        # 2) Text loi dien hinh hien tren man hinh
        for xpath in EMAIL_ERROR_XPATHS:
            try:
                for el in sb.find_elements(By.XPATH, xpath):
                    try:
                        if not el.is_displayed():
                            continue
                        text = (el.text or "").strip()
                        return (text[:160] if text else "this email cannot be used")
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception:
        pass
    return None


def _get_email_error():
    """Wrapper tuong thich cu."""
    return _check_email_rejected()

CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='cloudflare']",
    "iframe[src*='challenge']",
    ".g-recaptcha",
    ".h-captcha",
    ".cf-turnstile",
    "#challenge-running",
    "[class*='captcha']",
    "[id*='captcha']",
]

def _captcha_visible(driver):
    """Có element captcha nào đang hiển thị không (chỉ dùng để nhắc người dùng)"""
    for selector in CAPTCHA_SELECTORS:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            if el.is_displayed():
                return True, selector
        except Exception:
            continue
    return False, None

def wait_register_complete(timeout=CAPTCHA_TIMEOUT_SECONDS):
    """
    Chờ đăng ký hoàn tất: trang rời form register hoặc nút 'Go To Proxy List'
    xuất hiện. Render countdown vào status để chống giật, không print nhiều dòng.
    """
    deadline = time.time() + timeout
    prompted = False
    while time.time() < deadline:
        try:
            if "register" not in sb.current_url.lower():
                return True
        except Exception:
            pass
        if _go_to_proxy_list_visible():
            return True

        found, selector = _captcha_visible(sb)
        if found and not prompted:
            prompted = True
            log("CAPTCHA", f"Phat hien captcha ({selector}) — hay giai thu cong!")

        remaining = max(0, int(deadline - time.time()))
        mm, ss = divmod(remaining, 60)
        try:
            set_status("WAITING CAPTCHA")
            set_stage(f"Giai captcha thu cong... con {mm:02d}:{ss:02d}")
            bump_searches(1)
            render()
        except Exception:
            pass
        time.sleep(2)

    return False


def wait_for_registration_result(timeout=CAPTCHA_TIMEOUT_SECONDS, settle_seconds=8):
    """Vong cho thong nhat sau click Sign Up. Poll 1s/lan, tra ve (result, detail).

    - "SUCCESS": thay nut Go To Proxy List trong popup / dashboard (detail = ly do).
    - "EMAIL_REJECTED": server tu choi mail (element loi DO hien thi).
    - "TIMEOUT": het gio ma chua co ket qua.
    Moi lan doi mail goi lai ham nay (reset deadline) de du gio giai captcha.
    Trong settle_seconds dau sau click: chi soi loi mail, bo qua SUCCESS.
    """
    deadline = time.time() + timeout
    try:
        settle_until = time.time() + max(0, int(settle_seconds))
    except Exception:
        settle_until = time.time() + 8
    prompted = False
    last_url_log = 0.0
    while time.time() < deadline:
        try:
            ok, reason = _check_registration_success(settle_until=settle_until)
            if ok:
                log("OK", f"Xac nhan tao acc xong ({reason})")
                return "SUCCESS", reason
            err = _check_email_rejected()
            if err:
                return "EMAIL_REJECTED", err

            found, selector = _captcha_visible(sb)
            if found and not prompted:
                prompted = True
                log("CAPTCHA", f"Phat hien captcha ({selector}) — hay giai thu cong!")

            remaining = max(0, int(deadline - time.time()))
            mm, ss = divmod(remaining, 60)
            try:
                set_status("WAITING CAPTCHA")
                set_stage(f"Giai captcha thu cong... con {mm:02d}:{ss:02d}")
                bump_searches(1)
                # Debug throttled: lo URL hien tai moi 15s de lan sau ket thi nhin log biet
                now = time.time()
                if now - last_url_log >= 15:
                    last_url_log = now
                    url = _current_url_lower()
                    if url:
                        push_activity("-", f"URL: {url[:90]}")
                render()
            except Exception:
                pass
        except Exception:
            pass
        time.sleep(1)

    # Het gio: check lan cuoi ca 2 cua de bao dung nguyen nhan
    try:
        ok, reason = _check_registration_success()
        if ok:
            log("OK", f"Xac nhan tao acc xong ({reason})")
            return "SUCCESS", reason
        err = _check_email_rejected()
        if err:
            return "EMAIL_REJECTED", err
    except Exception:
        pass
    return "TIMEOUT", ""

def reset_session():
    """Xóa cookie + localStorage của domain hiện tại (đăng xuất trước acc mới)"""
    try:
        sb.delete_all_cookies()
        sb.execute_script("try{localStorage.clear()}catch(e){}")
    except Exception:
        pass


def _queue_preview(n=4):
    try:
        out = []
        for nm in (names_list or [])[:n]:
            try:
                b = str(nm).strip().split("\n")[0].strip()
            except Exception:
                continue
            if b:
                out.append(b)
        return out
    except Exception:
        return []


def _refresh_queue():
    try:
        STATE.queue_items = _queue_preview(4)
        STATE.queue_total = len(names_list) if isinstance(names_list, list) else 0
    except Exception:
        pass


def _count_accounts_file():
    try:
        if not os.path.exists(ACCOUNTS_FILE):
            return 0
        c = 0
        with open(ACCOUNTS_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("Email:"):
                    c += 1
        return c
    except Exception:
        return 0


def _count_proxies_file():
    try:
        if not os.path.exists(PROXIES_FILE):
            return 0
        c = 0
        with open(PROXIES_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.strip():
                    c += 1
        return c
    except Exception:
        return 0

# ============================================================
# BƯỚC 1–5: ĐĂNG KÝ TÀI KHOẢN
# ============================================================
def register_account():
    sb.get(REGISTER_URL)
    reset_session()
    sb.get(REGISTER_URL)
    time.sleep(3)

    # ----- BƯỚC 1: NHẬP EMAIL (lần đầu) -----
    used_emails = set()
    email = _generate_single_email(used_emails)
    used_emails.add(email)
    try:
        STATE.account_name = email
        set_status("REGISTERING")
        set_stage(f"Filling form {email}")
        bump_searches(1)
        render()
    except Exception:
        pass

    email_ok = False
    for attempt in range(1, 4):
        if _fill_email_field(email):
            email_ok = True
            break
        if attempt < 3:
            time.sleep(3)

    if not email_ok:
        raise AccountFlowError("Không tìm thấy ô email sau 3 lần thử")

    # ----- BƯỚC 2: NHẬP PASSWORD -----
    password = generate_password()
    password_selectors = [
        "input[data-testid='password-input']",
        "input[autocomplete='current-password']",
        "input[type='password']",
    ]

    password_field_found = False
    for attempt in range(1, 4):
        for selector in password_selectors:
            try:
                password_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                password_field_found = True

                time.sleep(1)
                password_field.clear()
                password_field.send_keys(password)
                time.sleep(1)
                break
            except Exception:
                continue

        if password_field_found:
            break
        if attempt < 3:
            time.sleep(3)

    if not password_field_found:
        raise AccountFlowError("Không tìm thấy ô password sau 3 lần thử")

    # ----- BƯỚC 3: TICK CHECKBOX (Terms of Service) -----
    _tick_terms_checkbox()

    # ----- BƯỚC 4: VÒNG CHỜ THỐNG NHẤT (captcha + kết quả server) -----
    # Mỗi mail có tối đa 5 phút: giải captcha xong server trả SUCCESS hay
    # EMAIL_REJECTED đều bắt trong 1-2s, không ngâm hết giờ. Đổi mail = reset giờ.
    for email_attempt in range(1, MAX_EMAIL_RETRIES + 1):
        try:
            set_status("REGISTERING")
            set_stage(f"Sign Up {email} ({email_attempt}/{MAX_EMAIL_RETRIES})")
            render()
        except Exception:
            pass
        if not retry_step("Click nút Sign Up", _click_signup):
            raise AccountFlowError("Không click được nút Sign Up")

        result, detail = wait_for_registration_result(
            timeout=CAPTCHA_TIMEOUT_SECONDS, settle_seconds=8
        )

        if result == "SUCCESS":
            break

        if result == "EMAIL_REJECTED":
            if email_attempt >= MAX_EMAIL_RETRIES:
                raise AccountFlowError(
                    f"Email bị từ chối {MAX_EMAIL_RETRIES} lần liên tiếp "
                    f"(mail cuối {email}: {detail})"
                )
            old_email = email
            email = _generate_single_email(used_emails)
            used_emails.add(email)
            try:
                STATE.account_name = email
            except Exception:
                pass
            log("WARN", f"Email {old_email} bi tu choi sau captcha ({detail}) — thu mail khac ({email_attempt + 1}/{MAX_EMAIL_RETRIES}): {email}")
            try:
                set_status("RETRY EMAIL")
                set_stage(f"Retry {email}")
                render()
            except Exception:
                pass
            if not _fill_email_field(email):
                raise AccountFlowError("Không điền được email mới sau khi bị từ chối")
            _tick_terms_checkbox()
            continue

        # TIMEOUT: het 5 phut cho mail nay ma chua co ket qua
        raise AccountFlowError(
            "Vẫn còn ở form đăng ký sau 5 phút — đăng ký không thành công "
            "(captcha chưa giải / mạng treo / form lỗi)"
        )

    log("OK", f"Dang ky thanh cong {email} — da roi form register")

    return email, password

def save_account(email, password):
    """Append block account vào accounts.txt (API Key sẽ append vào đúng block sau)"""
    try:
        with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
            f.write(f"{'='*50}\nEmail: {email}\nPassword: {password}\nCreated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log("SAVE", f"Account luu {email} -> {ACCOUNTS_DISPLAY}")
    except Exception:
        log("WARN", "Không lưu được thông tin account vào file")

# ============================================================
# LẤY PROXY TỪ PROXY LIST
# ============================================================
def open_proxy_list():
    """
    Sau khi đăng ký có popup 'Send your first proxy request' — phải click
    'Go To Proxy List' mới hiện bảng proxy để scrape; nếu không thấy nút
    thì điều hướng thẳng URL proxy list.
    """
    go_btn_xpath = GO_TO_PROXY_LIST_XPATH
    try:
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, go_btn_xpath)))
        sb.execute_script("arguments[0].click();", btn)
        time.sleep(3)
        return
    except Exception:
        pass

    log("WARN", "Khong thay nut Go To Proxy List — dieu huong thang Proxy List")
    sb.get(PROXY_LIST_URL)
    time.sleep(5)

VIEW_MY_PROXY_LIST_XPATHS = [
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    "'abcdefghijklmnopqrstuvwxyz'), 'view my proxy list')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    "'abcdefghijklmnopqrstuvwxyz'), 'view proxy list')]",
    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
    "'abcdefghijklmnopqrstuvwxyz'), 'my proxy list')]",
]

VIEW_MY_PROXY_LIST_CSS = [
    "button[data-testid*='view-proxy']",
    "button[data-testid*='proxy-list']",
    "a[href*='proxy/list']",
]


def _click_view_my_proxy_list():
    """Click nut 'View My Proxy List' tren Dashboard (banner Congratulations).
    Bang proxy chi hien sau khi click. Tra ve True/False, khong bao gio raise."""
    try:
        for xpath in VIEW_MY_PROXY_LIST_XPATHS:
            try:
                for el in sb.find_elements(By.XPATH, xpath):
                    try:
                        if not el.is_displayed():
                            continue
                        sb.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});", el)
                        time.sleep(1)
                        sb.execute_script("arguments[0].click();", el)
                        time.sleep(5)
                        return True
                    except Exception:
                        continue
            except Exception:
                continue
        for selector in VIEW_MY_PROXY_LIST_CSS:
            try:
                for el in sb.find_elements(By.CSS_SELECTOR, selector):
                    try:
                        if not el.is_displayed():
                            continue
                        sb.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});", el)
                        time.sleep(1)
                        sb.execute_script("arguments[0].click();", el)
                        time.sleep(5)
                        return True
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception:
        pass
    return False


def extract_proxies():
    time.sleep(5)

    proxy_rows = sb.find_elements(By.CSS_SELECTOR, "div.MuiDataGrid-row")

    # Nhịp 2: đang ở Dashboard (banner Congratulations) thì click
    # 'View My Proxy List' để hiện bảng rồi mới cào.
    if not proxy_rows:
        try:
            set_stage("Khong thay rows — click View My Proxy List")
            render()
        except Exception:
            pass
        if _click_view_my_proxy_list():
            log("OK", "Da click View My Proxy List — cho bang hien")
            proxy_rows = sb.find_elements(By.CSS_SELECTOR, "div.MuiDataGrid-row")
        else:
            log("WARN", "Khong thay nut View My Proxy List")

    if not proxy_rows:
        raise Exception("No proxy rows found in table")

    proxies = []
    for idx, row in enumerate(proxy_rows, 1):
        try:
            proxy_address = row.find_element(By.CSS_SELECTOR, "div[data-field='proxy_address'] div.css-14xdbal").text
            port = row.find_element(By.CSS_SELECTOR, "div[data-field='port'] div.css-14xdbal").text
            username = row.find_element(By.CSS_SELECTOR, "div[data-field='username'] div.css-14xdbal").text
            password_val = row.find_element(By.CSS_SELECTOR, "div[data-field='password'] div.css-14xdbal").text

            proxy_string = f"{username}:{password_val}@{proxy_address}:{port}"
            proxies.append(proxy_string)
        except Exception as e:
            log("WARN", f"Lỗi đọc proxy ở dòng {idx}: {e}")
            continue

    if proxies:
        with open(PROXIES_FILE, "a", encoding="utf-8") as f:
            for proxy in proxies:
                f.write(proxy + "\n")
        return len(proxies)

    raise Exception("No proxies extracted")

def proxy_stage():
    try:
        set_status("FETCHING PROXY")
        set_stage("Mo Proxy List + scrape bang")
        render()
    except Exception:
        pass
    open_proxy_list()
    count = retry_step("Lấy proxy từ bảng", extract_proxies)
    if count:
        try:
            STATE.alive_proxies = _count_proxies_file()
        except Exception:
            pass
        log("SAVE", f"{count} proxies luu -> {PROXIES_DISPLAY} (tong {getattr(STATE, 'alive_proxies', count)})")
    return count

# ============================================================
# LẤY API KEY
# ============================================================
def open_api_keys_page():
    sb.get(API_KEYS_URL)
    time.sleep(5)

    # Đóng dialog/popup nếu có
    try:
        close_btn = sb.find_element(By.CSS_SELECTOR, "button[aria-label='Close']")
        if close_btn.is_displayed():
            close_btn.click()
            time.sleep(2)
    except Exception:
        pass

    # Xác nhận nút Create API Key có mặt trên trang
    for selector_type, selector in [
        (By.CSS_SELECTOR, "button[data-testid='create-api-key-button']"),
        (By.XPATH, "//button[contains(text(), 'Create API Key')]"),
    ]:
        try:
            sb.find_element(selector_type, selector)
            return True
        except Exception:
            continue

    raise Exception("Create API Key button not found")

# Key webshare: chuỗi đúng 40 ký tự [a-z0-9] (đối chiếu 10 key lịch sử trong accounts.txt)
API_KEY_RE = re.compile(r"^[a-z0-9]{40}$")
API_KEY_SCAN_RE = re.compile(r"(?<![a-z0-9])[a-z0-9]{40}(?![a-z0-9])")

def _find_api_key():
    """Quét key theo tầng: selectors cũ → giá trị input → regex trên page_source"""
    # 1) Selectors cũ (class CSS-in-JS có thể quay lại)
    for selector in [
        "td[data-testid='paginated-list-table-col'] div.css-14xdbal",
        "div.css-14xdbal",
    ]:
        try:
            for el in sb.find_elements(By.CSS_SELECTOR, selector):
                text = el.text.strip()
                if API_KEY_RE.fullmatch(text):
                    return text
        except Exception:
            continue
    # 2) Key nằm trong input (ô copy)
    try:
        for el in sb.find_elements(By.CSS_SELECTOR, "input"):
            value = (el.get_attribute("value") or "").strip()
            if API_KEY_RE.fullmatch(value):
                return value
    except Exception:
        pass
    # 3) Regex trên toàn bộ DOM — bắt được key dù class CSS đã đổi hoàn toàn
    try:
        m = API_KEY_SCAN_RE.search(sb.page_source)
        if m:
            return m.group(0)
    except Exception:
        pass
    return None

def _wait_for_api_key(timeout=30):
    """Poll đến 30 giây; vòng đầu thử bật toggle 'hiện key' rồi quét lại"""
    deadline = time.time() + timeout
    revealed = False
    while time.time() < deadline:
        key = _find_api_key()
        if key:
            return key
        # Key mới hay bị che bằng dấu chấm — bật toggle hiện key (chỉ 1 lần,
        # click lặp lại sẽ che key trở lại)
        if not revealed:
            revealed = True
            try:
                toggles = sb.find_elements(By.CSS_SELECTOR, "button[aria-label='toggle password visibility']")
                for tbtn in toggles[:3]:
                    tbtn.click()
                    time.sleep(1)
                    key = _find_api_key()
                    if key:
                        return key
            except Exception:
                pass
        time.sleep(2)
    return None

def api_key_stage():
    """Trả về (api_key, label) hoặc None nếu thất bại (acc vẫn tính là xong)"""
    try:
        set_status("FETCHING KEY")
        set_stage("Mo trang API Keys")
        render()
    except Exception:
        pass
    if not retry_step("Mở trang API Keys", open_api_keys_page):
        try:
            STATE.webhook_active = False
        except Exception:
            pass
        return None

    try:
        # Scroll đến nút Create API Key
        try:
            create_btn_el = sb.find_element(By.CSS_SELECTOR, "button[data-testid='create-api-key-button']")
            sb.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", create_btn_el)
            time.sleep(2)
        except Exception:
            log("WARN", "Khong scroll duoc toi nut Create API Key")

        # Click nút "Create API Key"
        create_clicked = False
        for selector_type, selector_value in [
            (By.CSS_SELECTOR, "button[data-testid='create-api-key-button']"),
            (By.XPATH, "//button[contains(text(), 'Create API Key')]"),
        ]:
            try:
                btn = wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                sb.execute_script("arguments[0].click();", btn)
                time.sleep(2)
                create_clicked = True
                break
            except Exception:
                continue

        if not create_clicked:
            raise Exception("Create API Key button not found")

        # Nhập label cho API key
        label_entered = False
        api_key_label = f"AutoKey_{time.strftime('%Y%m%d_%H%M%S')}"
        for selector_type, selector_value in [
            (By.CSS_SELECTOR, "input[data-testid='create-api-key-label-input']"),
            (By.CSS_SELECTOR, "input.MuiInputBase-input.MuiOutlinedInput-input"),
        ]:
            try:
                label_input = wait.until(EC.presence_of_element_located((selector_type, selector_value)))
                label_input.clear()
                label_input.send_keys(api_key_label)
                time.sleep(1)
                label_entered = True
                break
            except Exception:
                continue

        if not label_entered:
            raise Exception("API key label input not found")

        # Click nút "Create" (JS trả về true/false — phải kiểm tra kết quả)
        clicked = sb.execute_script("""
        const createButton = Array.from(document.querySelectorAll('button')).find(btn => btn.textContent.trim() === 'Create');
        if (createButton) {
            createButton.click();
            return true;
        }
        return false;
        """)
        if not clicked:
            raise Exception("Không tìm thấy nút 'Create' trong dialog")
        time.sleep(3)

        # Chờ key xuất hiện: quét đa tầng + bật toggle hiện key nếu cần
        api_key = _wait_for_api_key()
        if not api_key:
            raise Exception(f"API key not found (URL: {sb.current_url})")

        # Append API key vào block account hiện tại trong accounts.txt
        try:
            with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
                f.write(f"API Key: {api_key}\nLabel: {api_key_label}\n")
            try:
                STATE.webhook_active = True
            except Exception:
                pass
            log("SAVE", f"API Key luu -> {ACCOUNTS_DISPLAY} ({api_key[:8]}...)")
        except Exception as e:
            log("ERROR", f"Loi luu API key: {e}")

        return api_key, api_key_label

    except Exception as e:
        try:
            STATE.webhook_active = False
        except Exception:
            pass
        log("ERROR", f"Lay API key that bai: {short_error(e)}")
        log("WARN", "Ban co the lay API key thu cong tren browser")
        return None

# ============================================================
# 1 VÒNG ĐỜI CỦA 1 TÀI KHOẢN
# ============================================================
def run_one_account(index):
    try:
        STATE.account_id = str(index)
        STATE.account_name = "..."
        _refresh_queue()
        set_status("ACTIVE")
        set_stage(f"Start ACC #{index}")
        render()
    except Exception:
        pass
    push_activity("-", f"TAO TAI KHOAN #{index}")
    render()

    t_reg_start = time.time()
    reset_session()
    email, password = register_account()
    try:
        STATE.account_name = email
    except Exception:
        pass
    reg_secs = time.time() - t_reg_start
    try:
        STATE.loop_v1 = reg_secs
    except Exception:
        pass

    save_account(email, password)

    # Cong xac minh: acc co that khong moi duoc chuyen trang fetch proxy
    if not _verify_account_created():
        raise AccountFlowError(
            "Chua thay bang chung tao acc (nut Go To Proxy List) — "
            "khong chuyen sang fetch proxy"
        )

    t_data_start = time.time()
    n_proxies = proxy_stage()
    key_result = api_key_stage()
    data_secs = time.time() - t_data_start
    try:
        STATE.loop_v2 = data_secs
        STATE.bought_count = _count_accounts_file()
        STATE.alive_proxies = _count_proxies_file()
        STATE.webhook_active = bool(key_result)
    except Exception:
        pass

    if key_result:
        push_activity(">", f"ACC #{index} HOAN TAT {email} | {n_proxies if n_proxies else 0} proxy | key {key_result[0][:8]}...")
    else:
        push_activity(">", f"ACC #{index} HOAN TAT {email} | {n_proxies if n_proxies else 0} proxy | key FAIL")
        push_activity("*", "API Key khong lay duoc — lay thu cong tren browser")
    try:
        set_status("ACTIVE")
        set_stage(f"Done ACC #{index} in {reg_secs + data_secs:.1f}s")
        render()
    except Exception:
        pass

# ============================================================
# MAIN — vòng lặp tạo account liên tục, Ctrl+C để dừng
# ============================================================
def main():
    global sb, wait, names_list

    try:
        STATE.app_name = "WEBSHARE GEN"
        STATE.version = "v2.2.0"
        STATE.mode = "UC Headed | Retry5 Capt300s"
        STATE.fail_count = 0
        set_status("STARTING")
        set_stage("Loading names.txt")
        render()
    except Exception:
        pass

    if not os.path.exists(NAMES_FILE):
        log("ERROR", f"Thieu file input {NAMES_DISPLAY} — kiem tra lai duong dan")
        return
    try:
        names_list = io.open(NAMES_FILE, "r").readlines()
    except Exception as e:
        log("ERROR", f"Loi doc {NAMES_DISPLAY}: {e}")
        return
    try:
        STATE.bought_count = _count_accounts_file()
        STATE.alive_proxies = _count_proxies_file()
        _refresh_queue()
    except Exception:
        pass
    log("OK", f"Da load {len(names_list)} ten tu {NAMES_DISPLAY} | co san {STATE.bought_count} acc {STATE.alive_proxies} proxy")

    from seleniumbase import Driver
    try:
        set_status("STARTING")
        set_stage("Khoi dong browser UC")
        render()
    except Exception:
        pass
    sb = Driver(uc=True, headed=True)
    wait = WebDriverWait(sb, 10)
    suppress_tensorflow_logs()
    try:
        sb.maximize_window()
    except Exception:
        pass
    try:
        STATE.proxy_active = True
    except Exception:
        pass
    log("OK", "SeleniumBase UC Mode san sang")

    # Đếm số acc tiếp theo từ file để ACCOUNT #ID khớp thực tế
    try:
        account_num = _count_accounts_file()
    except Exception:
        account_num = 0
    consecutive_failures = 0
    try:
        STATE.fail_count = 0
    except Exception:
        pass
    while True:
        account_num += 1
        try:
            run_one_account(account_num)
            consecutive_failures = 0
            try:
                STATE.fail_count = 0
                render()
            except Exception:
                pass
        except InvalidSessionIdException:
            log("ERROR", "Browser da bi dong hoac crash — dung script")
            try:
                STATE.proxy_active = False
                set_status("STOPPED")
                render()
            except Exception:
                pass
            break
        except AccountFlowError as e:
            consecutive_failures += 1
            try:
                STATE.fail_count = consecutive_failures
            except Exception:
                pass
            log("ERROR", f"Acc #{account_num} that bai: {e}")
        except Exception as e:
            msg = short_error(e)
            if "invalid session id" in msg.lower():
                log("ERROR", "Browser da bi dong hoac crash — dung script")
                try:
                    STATE.proxy_active = False
                    set_status("STOPPED")
                    render()
                except Exception:
                    pass
                break
            consecutive_failures += 1
            try:
                STATE.fail_count = consecutive_failures
            except Exception:
                pass
            log("ERROR", f"Acc #{account_num} loi khong xac dinh: {msg}")

        if consecutive_failures >= 3:
            log("ERROR", "3 acc lien tiep that bai — dung de kiem tra browser/mang")
            try:
                set_status("STOPPED")
                render()
            except Exception:
                pass
            break

        countdown(5, "Next acc in")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("INFO", "Đã dừng (Ctrl+C). Browser vẫn đang mở — đóng thủ công khi cần.")
        try:
            input("Nhấn Enter để thoát...")
        except (EOFError, KeyboardInterrupt):
            pass
