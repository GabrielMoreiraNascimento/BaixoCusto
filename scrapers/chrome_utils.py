import subprocess
import re
import threading

chrome_init_lock = threading.Lock()

def obter_versao_chrome():
    """
    Deteta automaticamente a versão major do Google Chrome instalado no sistema.
    
    Estratégia (Windows):
      1. Tenta ler do Registo do Windows (HKEY_CURRENT_USER).
      2. Se falhar, tenta via PowerShell (leitura do .exe).
      3. Se falhar, tenta via linha de comandos (Linux/Mac).
      
    Retorna:
      int: O número major da versão (ex: 149), ou None se não conseguir detetar.
    """
    versao = None
    
    # --- Tentativa 1: Registo do Windows ---
    try:
        import winreg
        chave = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
        valor, _ = winreg.QueryValueEx(chave, "version")
        winreg.CloseKey(chave)
        versao = int(valor.split(".")[0])
        print(f"🔍 [Chrome Utils] Versão detetada via Registo do Windows: {valor} (major: {versao})")
        return versao
    except Exception:
        pass
    
    # --- Tentativa 2: PowerShell (Windows fallback) ---
    try:
        resultado = subprocess.run(
            ['powershell', '-Command', 
             '(Get-Item "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe").VersionInfo.FileVersion'],
            capture_output=True, text=True, timeout=10
        )
        if resultado.returncode == 0 and resultado.stdout.strip():
            valor = resultado.stdout.strip()
            versao = int(valor.split(".")[0])
            print(f"🔍 [Chrome Utils] Versão detetada via PowerShell: {valor} (major: {versao})")
            return versao
    except Exception:
        pass
    
    # --- Tentativa 3: Linha de comandos (Linux/Mac) ---
    try:
        for cmd in ['google-chrome --version', 'google-chrome-stable --version', 'chromium --version']:
            resultado = subprocess.run(
                cmd.split(), capture_output=True, text=True, timeout=10
            )
            if resultado.returncode == 0:
                numeros = re.findall(r'(\d+)\.', resultado.stdout)
                if numeros:
                    versao = int(numeros[0])
                    print(f"🔍 [Chrome Utils] Versão detetada via terminal: {resultado.stdout.strip()} (major: {versao})")
                    return versao
    except Exception:
        pass
    
    print("⚠️ [Chrome Utils] Não foi possível detetar a versão do Chrome. O undetected_chromedriver tentará auto-detetar.")
    return versao
