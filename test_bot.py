import unittest
import os
from fetcher import is_quality_news
from database import init_db, is_news_sent, mark_news_as_sent

class TestBotLogic(unittest.TestCase):
    
    def setUp(self):
        # Crear base de datos temporal o inicializar
        init_db()
        
    def test_anti_troll_filter(self):
        # Noticias válidas
        self.assertTrue(is_quality_news("Apple Announces New M4 Chips for MacBook Pro"))
        self.assertTrue(is_quality_news("OpenAI releases GPT-5 with major improvements in reasoning"))
        
        # Noticias troll / clickbait / inválidas
        self.assertFalse(is_quality_news("SHOCKING!!! YOU WON'T BELIEVE WHAT ELON MUSK DID!!!")) # Exceso mayúsculas y puntuación
        self.assertFalse(is_quality_news("Buy this new crypto memecoin pump scam")) # Palabras prohibidas
        self.assertFalse(is_quality_news("Short")) # Muy corto
        
    def test_database_logic(self):
        # Probar la inserción y comprobación de duplicados
        test_id = "test_news_123"
        mark_news_as_sent(test_id, "Test Title", "Test Source")
        
        # Debería devolver True porque ya existe
        self.assertTrue(is_news_sent(test_id))
        
        # Un ID que no existe debería devolver False
        self.assertFalse(is_news_sent("fake_id_999"))

if __name__ == '__main__':
    unittest.main()
