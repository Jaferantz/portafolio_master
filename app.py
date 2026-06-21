import sys
import os

# Agregar portfolio_master al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'portfolio_master'))

# Intentar importar desde dashboard.app
try:
    from dashboard.app import main
except ImportError:
    # Si falla, intentar importar directamente
    sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
    from portfolio_master.dashboard.app import main

if __name__ == '__main__':
    main()
