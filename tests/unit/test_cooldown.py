# tests/test_cooldown.py
"""
Tests exhaustivos para el sistema de cooldown inteligente.
Cubre todos los casos de uso y edge cases del SmartCooldownManager.
"""
import pytest
from datetime import datetime, timezone
from freezegun import freeze_time

from alertio.cooldown import SmartCooldownManager, CooldownResult, CooldownConfig
from alertio.types import AlertType
from .conftest import create_alert


class TestCooldownBasics:
    """Tests básicos de funcionalidad del cooldown"""
    
    def test_first_alert_no_cooldown(self, cooldown_manager):
        """Primera alerta para un símbolo no debe tener cooldown"""
        alert = create_alert(symbol="AAPL", severity=0.08)
        
        result = cooldown_manager.calculate_cooldown(
            alert=alert,
            last_alert_time=None,
            consecutive_alerts=0
        )
        
        assert result.is_in_cooldown is False
        assert result.cooldown_days == 0
        assert result.consecutive_alerts == 0
        assert result.last_alert_time is None
        assert "Primera alerta" in result.reason
    
    def test_cooldown_result_structure(self, cooldown_manager):
        """Verificar que CooldownResult tiene todos los campos esperados"""
        alert = create_alert()
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        # Verificar que tiene todos los atributos
        assert hasattr(result, 'is_in_cooldown')
        assert hasattr(result, 'cooldown_days')
        assert hasattr(result, 'reason')
        assert hasattr(result, 'last_alert_time')
        assert hasattr(result, 'consecutive_alerts')


class TestMagnitudeCooldown:
    """Tests para cooldown basado en magnitud del movimiento"""
    
    def test_small_magnitude_cooldown(self, cooldown_manager):
        """Movimiento pequeño (<5%) debe usar cooldown corto (1 día)"""
        alert = create_alert(
            symbol="AAPL",
            severity=0.03,  # 3% - pequeño
            violated_windows=[{
                'window': 5,
                'return_value': 0.03,
                'threshold': 0.025,
                'threshold_type': 'max',
                'severity': 0.03
            }]
        )
        
        # Usar un last_alert_time antiguo (hace 30 días) para verificar el cálculo
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        # El cooldown debe ser 1 día (small) o 2 días (ventana 5), se usa el mayor
        assert result.cooldown_days == 2.0  # window cooldown es mayor
        assert not result.is_in_cooldown  # No está en cooldown porque hace 30 días
    
    def test_medium_magnitude_cooldown(self, cooldown_manager, old_alert_time):
        """Movimiento mediano (5-15%) debe usar cooldown mediano (3 días)"""
        alert = create_alert(
            symbol="AAPL",
            severity=0.08,  # 8% - mediano
            violated_windows=[{
                'window': 5,
                'return_value': 0.08,
                'threshold': 0.05,
                'threshold_type': 'max',
                'severity': 0.08
            }]
        )
        
        result = cooldown_manager.calculate_cooldown(alert, old_alert_time, 0)
        
        # El cooldown debe ser 3 días (medium magnitude)
        assert result.cooldown_days == 3.0
        assert "cooldown por magnitud" in result.reason
        assert "mediano" in result.reason
    
    def test_large_magnitude_cooldown(self, cooldown_manager, old_alert_time):
        """Movimiento grande (>15%) debe usar cooldown largo (7 días)"""
        alert = create_alert(
            symbol="AAPL",
            severity=0.20,  # 20% - grande
            violated_windows=[{
                'window': 5,
                'return_value': 0.20,
                'threshold': 0.10,
                'threshold_type': 'max',
                'severity': 0.20
            }]
        )
        
        result = cooldown_manager.calculate_cooldown(alert, old_alert_time, 0)
        
        # El cooldown debe ser 7 días (large magnitude)
        assert result.cooldown_days == 7.0
        assert "cooldown por magnitud" in result.reason
        assert "grande" in result.reason
    
    def test_magnitude_boundaries(self, cooldown_manager, old_alert_time):
        """Verificar límites exactos entre categorías de magnitud"""
        # Justo debajo de 5% = small
        alert_small = create_alert(severity=0.049, violated_windows=[{
            'window': 1, 'return_value': 0.049, 'threshold': 0.04,
            'threshold_type': 'max', 'severity': 0.049
        }])
        result_small = cooldown_manager.calculate_cooldown(alert_small, old_alert_time, 0)
        
        # Justo en 5% = medium
        alert_medium = create_alert(severity=0.05, violated_windows=[{
            'window': 1, 'return_value': 0.05, 'threshold': 0.04,
            'threshold_type': 'max', 'severity': 0.05
        }])
        result_medium = cooldown_manager.calculate_cooldown(alert_medium, old_alert_time, 0)
        
        # Justo en 15% = medium
        alert_medium2 = create_alert(severity=0.149, violated_windows=[{
            'window': 1, 'return_value': 0.149, 'threshold': 0.10,
            'threshold_type': 'max', 'severity': 0.149
        }])
        result_medium2 = cooldown_manager.calculate_cooldown(alert_medium2, old_alert_time, 0)
        
        # En 15% o más = large
        alert_large = create_alert(severity=0.15, violated_windows=[{
            'window': 1, 'return_value': 0.15, 'threshold': 0.10,
            'threshold_type': 'max', 'severity': 0.15
        }])
        result_large = cooldown_manager.calculate_cooldown(alert_large, old_alert_time, 0)
        
        assert result_small.cooldown_days < result_medium.cooldown_days
        assert result_medium2.cooldown_days < result_large.cooldown_days
    
    def test_multiple_violations_increase_magnitude(self, cooldown_manager, old_alert_time):
        """Múltiples violaciones deben aumentar la magnitud percibida"""
        # Una sola violación
        alert_single = create_alert(
            severity=0.08,
            violated_windows=[{
                'window': 5, 'return_value': 0.08, 'threshold': 0.05,
                'threshold_type': 'max', 'severity': 0.08
            }]
        )
        
        # Tres violaciones con misma severidad máxima
        alert_multiple = create_alert(
            severity=0.08,
            violated_windows=[
                {'window': 5, 'return_value': 0.08, 'threshold': 0.05,
                 'threshold_type': 'max', 'severity': 0.08},
                {'window': 10, 'return_value': 0.09, 'threshold': 0.07,
                 'threshold_type': 'max', 'severity': 0.09},
                {'window': 20, 'return_value': 0.10, 'threshold': 0.08,
                 'threshold_type': 'max', 'severity': 0.10}
            ]
        )
        
        result_single = cooldown_manager.calculate_cooldown(alert_single, old_alert_time, 0)
        result_multiple = cooldown_manager.calculate_cooldown(alert_multiple, old_alert_time, 0)
        
        # El cooldown con múltiples violaciones debe ser mayor
        assert result_multiple.cooldown_days > result_single.cooldown_days


class TestWindowCooldown:
    """Tests para cooldown basado en ventana de tiempo"""
    
    def test_1_day_window_cooldown(self, cooldown_manager, old_alert_time):
        """Ventana de 1 día con severity muy baja"""
        alert = create_alert(
            severity=0.03,  # 3% = small magnitude (1d)
            violated_windows=[{
                'window': 1,
                'return_value': 0.03,
                'threshold': 0.02,
                'threshold_type': 'max',
                'severity': 0.03
            }]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        # Con severity 3% (small=1d) y ventana 1d (0.5d), usa el mayor: 1d
        assert result.cooldown_days == 1.0
    
    def test_5_day_window_cooldown(self, cooldown_manager, old_alert_time):
        """Ventana de 5 días debe usar cooldown de 2 días"""
        alert = create_alert(
            severity=0.03,
            violated_windows=[{
                'window': 5,
                'return_value': 0.03,
                'threshold': 0.02,
                'threshold_type': 'max',
                'severity': 0.03
            }]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        assert result.cooldown_days == 2.0
    
    def test_10_day_window_cooldown(self, cooldown_manager, old_alert_time):
        """Ventana de 10 días debe usar cooldown de 3 días"""
        alert = create_alert(
            severity=0.03,
            violated_windows=[{
                'window': 10,
                'return_value': 0.03,
                'threshold': 0.02,
                'threshold_type': 'max',
                'severity': 0.03
            }]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        assert result.cooldown_days == 3.0
    
    def test_20_day_window_cooldown(self, cooldown_manager, old_alert_time):
        """Ventana de 20 días debe usar cooldown de 7 días"""
        alert = create_alert(
            severity=0.03,
            violated_windows=[{
                'window': 20,
                'return_value': 0.03,
                'threshold': 0.02,
                'threshold_type': 'max',
                'severity': 0.03
            }]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        assert result.cooldown_days == 7.0
    
    def test_multiple_windows_use_shortest(self, cooldown_manager, old_alert_time):
        """Con múltiples ventanas violadas, usa ventana más corta con multiplicador"""
        alert = create_alert(
            severity=0.05,  # 5% = medium (3d)
            violated_windows=[
                {'window': 5, 'return_value': 0.05, 'threshold': 0.03,
                 'threshold_type': 'max', 'severity': 0.05},
                {'window': 10, 'return_value': 0.06, 'threshold': 0.04,
                 'threshold_type': 'max', 'severity': 0.06},
                {'window': 20, 'return_value': 0.07, 'threshold': 0.05,
                 'threshold_type': 'max', 'severity': 0.07}
            ]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        # Magnitude (medium=3d) vs Window (min=5d -> 2d base * 1.6 multiplier = 3.2d)
        # Se usa el mayor: 3.2d
        assert result.cooldown_days == pytest.approx(3.2, rel=0.01)
    
    def test_multiple_windows_multiplier(self, cooldown_manager, old_alert_time):
        """Múltiples ventanas violadas deben aplicar multiplicador"""
        # Una ventana
        alert_single = create_alert(
            severity=0.03,
            violated_windows=[{
                'window': 5, 'return_value': 0.03, 'threshold': 0.02,
                'threshold_type': 'max', 'severity': 0.03
            }]
        )
        
        # Dos ventanas
        alert_double = create_alert(
            severity=0.03,
            violated_windows=[
                {'window': 5, 'return_value': 0.03, 'threshold': 0.02,
                 'threshold_type': 'max', 'severity': 0.03},
                {'window': 10, 'return_value': 0.04, 'threshold': 0.03,
                 'threshold_type': 'max', 'severity': 0.04}
            ]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result_single = cooldown_manager.calculate_cooldown(alert_single, old_time, 0)
        result_double = cooldown_manager.calculate_cooldown(alert_double, old_time, 0)
        
        # El cooldown con 2 ventanas debe ser mayor por el multiplicador
        # single: max(1d magnitude, 2d window) = 2d
        # double: max(1d magnitude, min(5,10)=5 -> 2d * 1.3) = 2.6d
        assert result_single.cooldown_days == 2.0
        assert result_double.cooldown_days == pytest.approx(2.6, rel=0.01)
        assert result_double.cooldown_days > result_single.cooldown_days


class TestProgressiveCooldown:
    """Tests para cooldown progresivo (alertas consecutivas)"""
    
    def test_no_progressive_multiplier_first_time(self, cooldown_manager):
        """Primera alerta no debe tener multiplicador progresivo"""
        alert = create_alert(severity=0.08)
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, consecutive_alerts=0)
        
        # No debe haber mención de multiplicador progresivo
        assert "multiplicador progresivo" not in result.reason
    
    def test_progressive_multiplier_applied(self, cooldown_manager, old_alert_time):
        """Alertas consecutivas deben aplicar multiplicador progresivo"""
        alert = create_alert(severity=0.08)
        
        # 0 alertas consecutivas
        result_0 = cooldown_manager.calculate_cooldown(alert, old_alert_time, consecutive_alerts=0)
        
        # 1 alerta consecutiva
        result_1 = cooldown_manager.calculate_cooldown(alert, old_alert_time, consecutive_alerts=1)
        
        # 3 alertas consecutivas
        result_3 = cooldown_manager.calculate_cooldown(alert, old_alert_time, consecutive_alerts=3)
        
        # Los cooldowns deben ir aumentando
        assert result_1.cooldown_days > result_0.cooldown_days
        assert result_3.cooldown_days > result_1.cooldown_days
        
        # Verificar multiplicadores específicos
        # 0 alertas: x1.0
        # 1 alerta: x1.5 (1.0 + 1*0.5)
        # 3 alertas: x2.5 (1.0 + 3*0.5)
        assert result_1.cooldown_days == result_0.cooldown_days * 1.5
        assert result_3.cooldown_days == result_0.cooldown_days * 2.5
    
    def test_progressive_multiplier_max_cap(self, cooldown_manager):
        """Multiplicador progresivo debe tener un límite máximo (3.0)"""
        alert = create_alert(severity=0.08)
        
        # Muchas alertas consecutivas que excederían el límite
        # Con multiplier=0.5, necesitamos (3.0-1.0)/0.5 = 4 alertas para llegar al cap
        result_4 = cooldown_manager.calculate_cooldown(alert, None, consecutive_alerts=4)
        result_10 = cooldown_manager.calculate_cooldown(alert, None, consecutive_alerts=10)
        
        # Ambos deben tener el mismo cooldown (máximo)
        base_cooldown = cooldown_manager.calculate_cooldown(alert, None, consecutive_alerts=0).cooldown_days
        assert result_4.cooldown_days == base_cooldown * 3.0
        assert result_10.cooldown_days == base_cooldown * 3.0
    
    def test_progressive_disabled(self):
        """Cuando progressive está deshabilitado, no debe aplicar multiplicador"""
        config = CooldownConfig(
            base_days=3,
            magnitude_cooldowns={"small": 1, "medium": 3, "large": 7},
            window_cooldowns={1: 0.5, 5: 2, 10: 3, 20: 7},
            progressive_enabled=False,  # Deshabilitado
            progressive_multiplier=0.5,
            max_progressive_multiplier=3.0
        )
        manager = SmartCooldownManager(config)
        
        alert = create_alert(severity=0.08)
        
        result_0 = manager.calculate_cooldown(alert, None, consecutive_alerts=0)
        result_5 = manager.calculate_cooldown(alert, None, consecutive_alerts=5)
        
        # Deben tener el mismo cooldown
        assert result_0.cooldown_days == result_5.cooldown_days
        assert "multiplicador progresivo" not in result_5.reason
    
    def test_extreme_movements_ignore_progressive(self, cooldown_manager, old_alert_time):
        """Movimientos extremos (>20%) deben ignorar el multiplicador progresivo"""
        # Movimiento extremo de 25%
        alert_extreme = create_alert(
            severity=0.25,  # 25% - extremo
            violated_windows=[{
                'window': 5,
                'return_value': 0.25,
                'threshold': 0.10,
                'threshold_type': 'max',
                'severity': 0.25
            }]
        )
        
        # Con 0 alertas consecutivas
        result_0 = cooldown_manager.calculate_cooldown(alert_extreme, old_alert_time, consecutive_alerts=0)
        
        # Con 5 alertas consecutivas (debería ignorar el progresivo)
        result_5 = cooldown_manager.calculate_cooldown(alert_extreme, old_alert_time, consecutive_alerts=5)
        
        # Deben tener el MISMO cooldown (sin multiplicador progresivo)
        assert result_0.cooldown_days == result_5.cooldown_days
        assert result_5.cooldown_days == 7.0  # Solo el cooldown large
        assert "multiplicador progresivo" not in result_5.reason
        
        # Verificar que movimientos NO extremos SÍ aplican progresivo
        alert_normal = create_alert(
            severity=0.15,  # 15% - no extremo
            violated_windows=[{
                'window': 5,
                'return_value': 0.15,
                'threshold': 0.10,
                'threshold_type': 'max',
                'severity': 0.15
            }]
        )
        
        result_normal_5 = cooldown_manager.calculate_cooldown(alert_normal, old_alert_time, consecutive_alerts=5)
        
        # Movimiento normal SÍ debe tener progresivo
        assert result_normal_5.cooldown_days > 7.0  # Mayor por el progresivo
        assert "multiplicador progresivo" in result_normal_5.reason


class TestCooldownState:
    """Tests para verificar el estado del cooldown (activo/inactivo)"""
    
    @freeze_time("2025-01-01 12:00:00")
    def test_in_cooldown_recent_alert(self, cooldown_manager):
        """Alerta reciente debe estar en cooldown"""
        alert = create_alert(severity=0.08)  # 3 días de cooldown
        
        # Última alerta hace 1 día
        last_alert_time = datetime(2024, 12, 31, 12, 0, 0, tzinfo=timezone.utc)
        
        result = cooldown_manager.calculate_cooldown(alert, last_alert_time, 0)
        
        assert result.is_in_cooldown is True
        assert result.cooldown_days == 3.0
    
    @freeze_time("2025-01-01 12:00:00")
    def test_not_in_cooldown_old_alert(self, cooldown_manager):
        """Alerta antigua debe NO estar en cooldown"""
        alert = create_alert(severity=0.08)  # 3 días de cooldown
        
        # Última alerta hace 5 días (más que el cooldown de 3 días)
        last_alert_time = datetime(2024, 12, 27, 12, 0, 0, tzinfo=timezone.utc)
        
        result = cooldown_manager.calculate_cooldown(alert, last_alert_time, 0)
        
        assert result.is_in_cooldown is False
        assert result.cooldown_days == 3.0
    
    @freeze_time("2025-01-01 12:00:00")
    def test_cooldown_exact_boundary(self, cooldown_manager):
        """Verificar comportamiento exacto en el límite del cooldown"""
        alert = create_alert(severity=0.08)  # 3 días de cooldown
        
        # Exactamente 3 días atrás (límite)
        last_alert_time = datetime(2024, 12, 29, 12, 0, 0, tzinfo=timezone.utc)
        
        result = cooldown_manager.calculate_cooldown(alert, last_alert_time, 0)
        
        # Debe estar fuera del cooldown (>=)
        assert result.is_in_cooldown is False
    
    @freeze_time("2025-01-01 12:00:00")
    def test_short_cooldown_hours(self, cooldown_manager):
        """Cooldown con ventana corta (1d)"""
        alert = create_alert(
            severity=0.03,  # 3% = small (1d magnitude)
            violated_windows=[{
                'window': 1, 'return_value': 0.03, 'threshold': 0.02,
                'threshold_type': 'max', 'severity': 0.03
            }]
        )  # Cooldown: max(1d magnitude, 0.5d window) = 1d
        
        # Hace 6 horas (dentro del cooldown de 1d)
        last_alert_time = datetime(2025, 1, 1, 6, 0, 0, tzinfo=timezone.utc)
        result_6h = cooldown_manager.calculate_cooldown(alert, last_alert_time, 0)
        
        # Hace 26 horas (fuera del cooldown de 1d)
        last_alert_time = datetime(2024, 12, 31, 10, 0, 0, tzinfo=timezone.utc)
        result_26h = cooldown_manager.calculate_cooldown(alert, last_alert_time, 0)
        
        assert result_6h.is_in_cooldown is True
        assert result_26h.is_in_cooldown is False


class TestCombinedCooldown:
    """Tests para combinación de diferentes tipos de cooldown"""
    
    def test_magnitude_dominates_window(self, cooldown_manager, old_alert_time):
        """Cuando magnitud es mayor que ventana, debe dominar"""
        # Magnitud grande (7d) en ventana corta (0.5d)
        alert = create_alert(
            severity=0.20,  # Grande = 7 días
            violated_windows=[{
                'window': 1,  # 0.5 días
                'return_value': 0.20,
                'threshold': 0.10,
                'threshold_type': 'max',
                'severity': 0.20
            }]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        # Debe usar el cooldown por magnitud (7d)
        assert result.cooldown_days == 7.0
        assert "magnitud" in result.reason
    
    def test_window_dominates_magnitude(self, cooldown_manager, old_alert_time):
        """Cuando ventana es mayor que magnitud, debe dominar"""
        # Magnitud pequeña (1d) en ventana larga (7d)
        alert = create_alert(
            severity=0.03,  # Pequeño = 1 día
            violated_windows=[{
                'window': 20,  # 7 días
                'return_value': 0.03,
                'threshold': 0.02,
                'threshold_type': 'max',
                'severity': 0.03
            }]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        # Debe usar el cooldown por ventana (7d)
        assert result.cooldown_days == 7.0
        assert "ventana" in result.reason
    
    def test_progressive_multiplies_base_cooldown(self, cooldown_manager, old_alert_time):
        """Multiplicador progresivo debe aplicarse sobre el cooldown base"""
        alert = create_alert(severity=0.08)  # 3 días base
        
        # Con 2 alertas consecutivas: 3 * (1 + 2*0.5) = 3 * 2.0 = 6
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, consecutive_alerts=2)
        
        assert result.cooldown_days == 6.0
        assert "multiplicador progresivo" in result.reason
        assert "2 alertas consecutivas" in result.reason


class TestCooldownSummary:
    """Tests para el resumen legible del cooldown"""
    
    @freeze_time("2025-01-01 12:00:00")
    def test_summary_not_in_cooldown(self, cooldown_manager):
        """Resumen cuando no está en cooldown"""
        alert = create_alert(severity=0.08)
        
        summary = cooldown_manager.get_cooldown_summary(alert, None, 0)
        
        assert "Sin cooldown" in summary
        assert "Primera alerta" in summary
    
    @freeze_time("2025-01-01 12:00:00")
    def test_summary_in_cooldown(self, cooldown_manager):
        """Resumen cuando está en cooldown"""
        alert = create_alert(severity=0.08)
        last_alert_time = datetime(2024, 12, 31, 12, 0, 0, tzinfo=timezone.utc)
        
        summary = cooldown_manager.get_cooldown_summary(alert, last_alert_time, 0)
        
        assert "En cooldown" in summary
        assert "días" in summary
        assert "restantes" in summary
    
    @freeze_time("2025-01-01 12:00:00")
    def test_summary_includes_time_remaining(self, cooldown_manager):
        """Resumen debe incluir tiempo restante en horas"""
        alert = create_alert(severity=0.08)  # 3 días de cooldown
        last_alert_time = datetime(2024, 12, 31, 12, 0, 0, tzinfo=timezone.utc)  # Hace 1 día
        
        summary = cooldown_manager.get_cooldown_summary(alert, last_alert_time, 0)
        
        # Deben quedar 2 días = 48 horas
        assert "48.0h restantes" in summary or "48h restantes" in summary


class TestEdgeCases:
    """Tests para casos extremos y edge cases"""
    
    def test_zero_severity(self, cooldown_manager):
        """Severidad de 0 debe manejarse correctamente"""
        alert = create_alert(
            severity=0.0,
            violated_windows=[{
                'window': 5,
                'return_value': 0.0,
                'threshold': 0.0,
                'threshold_type': 'max',
                'severity': 0.0
            }]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        # Debe funcionar sin errores y usar cooldown small
        assert result.cooldown_days >= 0
        assert not result.is_in_cooldown
    
    def test_extreme_severity(self, cooldown_manager, old_alert_time):
        """Severidad muy alta debe manejarse correctamente"""
        alert = create_alert(
            severity=1.0,  # 100%
            violated_windows=[{
                'window': 5,
                'return_value': 1.0,
                'threshold': 0.1,
                'threshold_type': 'max',
                'severity': 1.0
            }]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        # Debe usar cooldown large
        assert result.cooldown_days == 7.0
    
    def test_negative_consecutive_alerts(self, cooldown_manager, old_alert_time):
        """Alertas consecutivas negativas deben tratarse como 0"""
        alert = create_alert(severity=0.08)
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, consecutive_alerts=-5)
        
        # No debe aplicar multiplicador negativo
        assert result.cooldown_days > 0
    
    def test_empty_violated_windows(self, cooldown_manager, old_alert_time):
        """Lista vacía de violated_windows debe usar cooldown base"""
        alert = create_alert(
            severity=0.08,
            violated_windows=[]
        )
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = cooldown_manager.calculate_cooldown(alert, old_time, 0)
        
        # Debe usar el cooldown base (3 días por configuración)
        assert result.cooldown_days == 3.0
    
    def test_custom_cooldown_config(self, old_alert_time):
        """Configuración personalizada debe aplicarse correctamente"""
        custom_config = CooldownConfig(
            base_days=5,
            magnitude_cooldowns={"small": 2, "medium": 5, "large": 10},
            window_cooldowns={1: 1.0, 5: 3, 10: 5, 20: 10},
            progressive_enabled=True,
            progressive_multiplier=1.0,
            max_progressive_multiplier=5.0
        )
        manager = SmartCooldownManager(custom_config)
        
        alert = create_alert(severity=0.08)  # Medium
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = manager.calculate_cooldown(alert, old_time, 0)
        
        # Debe usar los valores personalizados
        assert result.cooldown_days == 5.0  # medium magnitude
    
    @freeze_time("2025-01-01 12:00:00")
    def test_future_last_alert_time(self, cooldown_manager):
        """Última alerta en el futuro (caso raro) debe manejarse"""
        alert = create_alert(severity=0.08)
        
        # Última alerta en el futuro (error de datos)
        future_time = datetime(2025, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
        
        result = cooldown_manager.calculate_cooldown(alert, future_time, 0)
        
        # Debe estar en cooldown (tiempo negativo = aún en cooldown)
        assert result.is_in_cooldown is True
    
    def test_drop_alert_type(self, cooldown_manager):
        """Alertas de tipo DROP deben funcionar igual que RISE"""
        alert_drop = create_alert(
            severity=0.08,
            alert_type=AlertType.DROP
        )
        
        alert_rise = create_alert(
            severity=0.08,
            alert_type=AlertType.RISE
        )
        
        result_drop = cooldown_manager.calculate_cooldown(alert_drop, None, 0)
        result_rise = cooldown_manager.calculate_cooldown(alert_rise, None, 0)
        
        # Ambos deben tener el mismo cooldown
        assert result_drop.cooldown_days == result_rise.cooldown_days


class TestRealWorldScenarios:
    """Tests que simulan escenarios del mundo real"""
    
    @freeze_time("2025-01-01 12:00:00")
    def test_scenario_volatile_stock(self, cooldown_manager):
        """Stock volátil con múltiples alertas en corto tiempo"""
        alert = create_alert(symbol="GME", severity=0.25)
        
        # Primera alerta
        result1 = cooldown_manager.calculate_cooldown(alert, None, 0)
        assert not result1.is_in_cooldown
        
        # Segunda alerta 2 horas después
        time1 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        result2 = cooldown_manager.calculate_cooldown(alert, time1, 1)
        assert result2.is_in_cooldown  # Debe estar en cooldown
        
        # Tercera alerta 15 días después (fuera de cooldown de 14 días)
        time2 = datetime(2024, 12, 17, 12, 0, 0, tzinfo=timezone.utc)
        result3 = cooldown_manager.calculate_cooldown(alert, time2, 2)
        assert not result3.is_in_cooldown  # 15 días > 14 días cooldown
    
    @freeze_time("2025-01-01 12:00:00")
    def test_scenario_steady_decline(self, cooldown_manager):
        """Caída constante con alertas progresivas"""
        alert = create_alert(symbol="AAPL", severity=0.06, alert_type=AlertType.DROP)
        
        # Simular alertas consecutivas con cooldown progresivo
        times = [
            datetime(2024, 12, 25, 12, 0, 0, tzinfo=timezone.utc),  # 7 días atrás
            datetime(2024, 12, 20, 12, 0, 0, tzinfo=timezone.utc),  # 12 días atrás
            datetime(2024, 12, 10, 12, 0, 0, tzinfo=timezone.utc),  # 22 días atrás
        ]
        
        for i, time in enumerate(times):
            result = cooldown_manager.calculate_cooldown(alert, time, i)
            # Cada vez debe tener más cooldown por el progresivo
            expected_base = 3.0  # medium
            expected_multiplier = 1.0 + (i * 0.5)
            assert result.cooldown_days == expected_base * expected_multiplier
    
    def test_scenario_multiple_symbols(self, cooldown_manager):
        """Múltiples símbolos deben tener cooldowns independientes"""
        alert_aapl = create_alert(symbol="AAPL", severity=0.08)
        alert_tsla = create_alert(symbol="TSLA", severity=0.08)
        
        result_aapl = cooldown_manager.calculate_cooldown(alert_aapl, None, 0)
        result_tsla = cooldown_manager.calculate_cooldown(alert_tsla, None, 0)
        
        # Ambos deben tener cooldowns calculados independientemente
        assert result_aapl.cooldown_days == result_tsla.cooldown_days
        assert not result_aapl.is_in_cooldown
        assert not result_tsla.is_in_cooldown


class TestCooldownIntegration:
    """Tests de integración con otros componentes"""
    
    def test_cooldown_with_real_config_structure(self, old_alert_time):
        """Verificar que funciona con estructura real de config"""
        from alertio.config import CooldownConfig
        
        # Simular configuración real desde YAML
        config = CooldownConfig(
            base_days=3,
            magnitude_cooldowns={
                "small": 1,
                "medium": 3,
                "large": 7,
            },
            window_cooldowns={
                1: 0.5,
                5: 2,
                10: 3,
                20: 7,
            },
            progressive_enabled=True,
            progressive_multiplier=0.5,
            max_progressive_multiplier=3.0
        )
        
        manager = SmartCooldownManager(config)
        alert = create_alert(severity=0.08)
        
        old_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = manager.calculate_cooldown(alert, old_time, 0)
        
        assert result is not None
        assert isinstance(result, CooldownResult)
        assert result.cooldown_days > 0

