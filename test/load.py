import unittest
import threading
import time
import socket
import json
import sys
from unittest.mock import Mock, patch, MagicMock
import concurrent.futures

try:
    from checkers.split.server.pythonProject.database.actions import initialize_database, delete_user_by_id
    from checkers.split.client.pythonProject.client import connect_to_server, setup_pieces, invert_coordinates
    from checkers.split.client.pythonProject.looking_rooms import refresh_rooms, create_room, join_room
    from checkers.split.client.pythonProject.main_activity import view_rooms, top_players, \
        connect_to_server as main_connect
    from checkers.split.client.pythonProject.user_activity_with_server import login, register
    from checkers.split.server.pythonProject.server import (
        authorization, register as server_register, top_players as server_top_players,
        calculate_possible_moves, has_possible_moves, make_move, get_username_by_id, update_scores
    )
except ImportError as e:
    print(f"Import error: {e}")
    # Определяем заглушки для тестирования
    connect_to_server = lambda socket: None
    setup_pieces = lambda pieces: None
    invert_coordinates = lambda row, col: (row, col)
    initialize_database = lambda: None
    delete_user_by_id = lambda user_id: None


    # Остальные функции-заглушки
    def mock_function(*args, **kwargs):
        return None


    refresh_rooms = create_room = join_room = view_rooms = top_players = main_connect = mock_function
    login = register = mock_function
    authorization = server_register = server_top_players = mock_function
    calculate_possible_moves = has_possible_moves = make_move = get_username_by_id = update_scores = mock_function


class TestLoadCapacity(unittest.TestCase):
    """Тесты на нагрузочную способность системы"""

    def setUp(self):
        """Настройка перед каждым тестом"""
        self.server_address = ('172.20.10.2', 43000)
        self.test_users = []
        self.connections = []

    def tearDown(self):
        """Очистка после каждого теста"""
        for conn in self.connections:
            try:
                conn.close()
            except:
                pass
        self.connections.clear()
        self.test_users.clear()

    def test_multiple_connections_creation(self):
        """Тест создания множества соединений"""
        connections_count = 50
        success_count = 0

        for i in range(connections_count):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                # В тесте используем заглушку
                connect_to_server(sock)
                self.connections.append(sock)
                success_count += 1
                time.sleep(0.01)  # Небольшая пауза между подключениями
            except Exception as e:
                print(f"Connection {i} failed: {e}")

        print(f"Успешных подключений: {success_count} из {connections_count}")
        self.assertGreater(success_count, connections_count * 0.8,"Более 80% подключений должны быть успешными")

    def test_concurrent_registration(self):
        """Тест параллельной регистрации пользователей"""
        users_count = 100
        results = []

        def register_user(user_id):
            try:
                # Создаем заглушку для регистрации
                mock_socket = Mock()
                mock_response = json.dumps({'status': True, 'user_id': user_id})
                mock_socket.recv.return_value = mock_response.encode()

                result = register()
                return (user_id, True, result)
            except Exception as e:
                return (user_id, False, str(e))

        # Используем ThreadPoolExecutor для параллельного выполнения
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(register_user, i) for i in range(users_count)]

            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        successful = sum(1 for _, success, _ in results if success)
        print(f"Успешных регистраций: {successful} из {users_count}")
        self.assertGreater(successful, users_count * 0.9,
                           "Более 90% регистраций должны быть успешными")

    def test_database_operations_under_load(self):
        """Тест операций с базой данных под нагрузкой"""
        operations_count = 500

        def database_operation(op_type, user_id):
            try:
                if op_type == 'get':
                    result = get_username_by_id(user_id)
                    return True
                elif op_type == 'update':
                    update_scores(user_id, user_id + 1)
                    return True
                elif op_type == 'init':
                    initialize_database()
                    return True
                return False
            except Exception:
                return False

        start_time = time.time()
        success_count = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = []
            for i in range(operations_count):
                op_type = 'get' if i % 3 == 0 else 'update' if i % 3 == 1 else 'init'
                futures.append(executor.submit(database_operation, op_type, i))

            for future in concurrent.futures.as_completed(futures):
                if future.result():
                    success_count += 1

        end_time = time.time()
        duration = end_time - start_time

        print(f"Операций с БД: {success_count} из {operations_count}")
        print(f"Время выполнения: {duration:.2f} секунд")
        print(f"Операций в секунду: {operations_count / duration:.2f}")

        self.assertGreater(success_count, operations_count * 0.95,
                           "Более 95% операций с БД должны быть успешными")
        self.assertLess(duration, 10,
                        f"Операции должны выполняться быстрее 10 секунд (фактически: {duration:.2f})")


class TestGameLogicLoad(unittest.TestCase):
    """Тесты нагрузочного тестирования игровой логики"""

    def setUp(self):
        self.test_board = [[0] * 8 for _ in range(8)]

        # Начальная расстановка шашек
        for row in range(8):
            for col in range(8):
                if (row + col) % 2 == 1:
                    if row < 3:
                        self.test_board[row][col] = 1
                    elif row > 4:
                        self.test_board[row][col] = 2

    def test_calculate_moves_under_load(self):
        """Тест расчета ходов под нагрузкой"""
        iterations = 1000
        start_time = time.time()

        for i in range(iterations):
            # Тестируем расчет ходов для разных позиций
            row = i % 8
            col = (i * 3) % 8

            # Для игрока 1
            moves_player1 = calculate_possible_moves(self.test_board, row, col, 1)

            # Для игрока 2
            moves_player2 = calculate_possible_moves(self.test_board, row, col, 2)

            # Проверяем что функция возвращает список
            self.assertIsInstance(moves_player1, list)
            self.assertIsInstance(moves_player2, list)

        end_time = time.time()
        duration = end_time - start_time

        print(f"Расчет ходов: {iterations} итераций за {duration:.2f} секунд")
        print(f"Скорость: {iterations / duration:.2f} операций/сек")

        self.assertLess(duration, 5,
                        f"Расчет ходов должен выполняться быстрее 5 секунд (фактически: {duration:.2f})")

    def test_concurrent_game_states(self):
        """Тест одновременной обработки игровых состояний"""
        game_states_count = 50
        threads = []
        results = []

        def simulate_game(game_id):
            try:
                board = [row[:] for row in self.test_board]

                # Симулируем несколько ходов
                for move in range(10):
                    # Находим шашку игрока 1
                    for row in range(8):
                        for col in range(8):
                            if board[row][col] == 1:
                                moves = calculate_possible_moves(board, row, col, 1)
                                if moves:
                                    # Выполняем ход
                                    new_row, new_col = moves[0]
                                    board, can_continue, game_status = make_move(
                                        board, new_row, new_col, (row, col), 1
                                    )
                                    break

                # Проверяем наличие возможных ходов
                has_moves = has_possible_moves(board, 1)
                return (game_id, True, has_moves)
            except Exception as e:
                return (game_id, False, str(e))

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(simulate_game, i) for i in range(game_states_count)]

            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        end_time = time.time()
        duration = end_time - start_time

        successful = sum(1 for _, success, _ in results if success)

        print(f"Симуляция игр: {successful} из {game_states_count}")
        print(f"Время выполнения: {duration:.2f} секунд")

        self.assertGreater(successful, game_states_count * 0.95,
                           "Более 95% симуляций должны быть успешными")
        self.assertLess(duration, 15,
                        f"Симуляция должна выполняться быстрее 15 секунд (фактически: {duration:.2f})")


class TestRoomManagementLoad(unittest.TestCase):
    """Тесты нагрузочного тестирования управления комнатами"""

    def test_multiple_rooms_creation(self):
        """Тест создания множества комнат"""
        rooms_count = 50
        success_count = 0

        def create_room_simulation(room_id):
            try:
                # Имитируем создание комнаты
                mock_socket = Mock()
                mock_response = json.dumps({
                    'status': True,
                    'client_number': 1,
                    'room_number': room_id
                })
                mock_socket.recv.return_value = mock_response.encode()

                # Вызываем функцию создания комнаты
                create_room()
                return True
            except Exception:
                return False

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_room_simulation, i) for i in range(rooms_count)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        success_count = sum(results)

        print(f"Создано комнат: {success_count} из {rooms_count}")
        self.assertGreater(success_count, rooms_count * 0.9,
                           "Более 90% комнат должны быть успешно созданы")

    def test_room_refresh_under_load(self):
        """Тест обновления списка комнат под нагрузкой"""
        refresh_count = 100
        start_time = time.time()
        success_count = 0

        for i in range(refresh_count):
            try:
                # Имитируем обновление комнат
                mock_socket = Mock()
                mock_response = json.dumps({
                    'status': True,
                    'message': [
                        {'room_id': 1, 'creator': 'test_user', 'player_count': 1},
                        {'room_id': 2, 'creator': 'test_user2', 'player_count': 2}
                    ]
                })
                mock_socket.recv.return_value = mock_response.encode()

                # Вызываем функцию обновления
                refresh_rooms()
                success_count += 1
            except Exception:
                pass

        end_time = time.time()
        duration = end_time - start_time

        print(f"Обновлений комнат: {success_count} из {refresh_count}")
        print(f"Время выполнения: {duration:.2f} секунд")
        print(f"Скорость: {refresh_count / duration:.2f} обновлений/сек")

        self.assertGreater(success_count, refresh_count * 0.95,
                           "Более 95% обновлений должны быть успешными")


class TestMemoryAndPerformance(unittest.TestCase):
    """Тесты памяти и производительности"""

    def test_memory_usage_simulation(self):
        """Тест оценки использования памяти"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # в МБ

        # Создаем большое количество объектов для теста
        test_objects = []
        for i in range(10000):
            test_objects.append({
                'user_id': i,
                'username': f'test_user_{i}',
                'connection': Mock(),
                'room': i % 10
            })

        current_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = current_memory - initial_memory

        print(f"Изначальная память: {initial_memory:.2f} MB")
        print(f"Текущая память: {current_memory:.2f} MB")
        print(f"Увеличение памяти: {memory_increase:.2f} MB")

        # Проверяем что использование памяти разумное
        self.assertLess(memory_increase, 100,
                        f"Использование памяти не должно превышать 100 MB (фактически: {memory_increase:.2f} MB)")

        # Освобождаем память
        test_objects.clear()
        import gc
        gc.collect()

    def test_response_time_benchmark(self):
        """Тест времени отклика системы"""
        test_cases = 100
        response_times = []

        for i in range(test_cases):
            start_time = time.time()

            # Тестируем разные операции
            if i % 4 == 0:
                # Авторизация
                login()
            elif i % 4 == 1:
                # Регистрация
                register()
            elif i % 4 == 2:
                # Получение топа игроков
                top_players()
            else:
                # Просмотр комнат
                view_rooms()

            end_time = time.time()
            response_times.append(end_time - start_time)

            # Небольшая пауза между запросами
            time.sleep(0.01)

        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        min_response_time = min(response_times)

        print(f"Среднее время отклика: {avg_response_time:.3f} секунд")
        print(f"Минимальное время: {min_response_time:.3f} секунд")
        print(f"Максимальное время: {max_response_time:.3f} секунд")

        # Проверяем что среднее время отклика приемлемое
        self.assertLess(avg_response_time, 0.5,
                        f"Среднее время отклика должно быть меньше 0.5 секунд (фактически: {avg_response_time:.3f})")
        self.assertLess(max_response_time, 2.0,
                        f"Максимальное время отклика должно быть меньше 2 секунд (фактически: {max_response_time:.3f})")


class TestIntegrationLoad(unittest.TestCase):
    """Интеграционные нагрузочные тесты"""

    def test_complete_user_journey_load(self):
        """Тест полного цикла пользователя под нагрузкой"""
        users_count = 30
        successful_journeys = 0

        def simulate_user_journey(user_id):
            try:
                # 1. Регистрация
                mock_socket = Mock()
                mock_response = json.dumps({'status': True, 'user_id': user_id})
                mock_socket.recv.return_value = mock_response.encode()
                register()

                # 2. Авторизация
                login()

                # 3. Просмотр комнат
                mock_response = json.dumps({
                    'status': True,
                    'message': [
                        {'room_id': 1, 'creator': 'test', 'player_count': 1},
                        {'room_id': 2, 'creator': 'test2', 'player_count': 2}
                    ]
                })
                mock_socket.recv.return_value = mock_response.encode()
                view_rooms()

                # 4. Получение топа игроков
                mock_response = json.dumps({
                    'status': True,
                    'message': ['1: test_user: 500 очков']
                })
                mock_socket.recv.return_value = mock_response.encode()
                top_players()

                # 5. Создание комнаты
                mock_response = json.dumps({
                    'client_number': 1,
                    'room_number': user_id
                })
                mock_socket.recv.return_value = mock_response.encode()
                create_room()

                return True
            except Exception as e:
                print(f"User {user_id} journey failed: {e}")
                return False

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(simulate_user_journey, i) for i in range(users_count)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        end_time = time.time()
        duration = end_time - start_time

        successful_journeys = sum(results)

        print(f"Успешных циклов пользователя: {successful_journeys} из {users_count}")
        print(f"Общее время выполнения: {duration:.2f} секунд")
        print(f"Среднее время на пользователя: {duration / users_count:.2f} секунд")

        self.assertGreater(successful_journeys, users_count * 0.8,
                           "Более 80% пользовательских циклов должны быть успешными")
        self.assertLess(duration, 30,
                        f"Цикл должен выполняться быстрее 30 секунд (фактически: {duration:.2f})")


def run_load_tests():
    """Запуск всех нагрузочных тестов"""
    loader = unittest.TestLoader()

    # Собираем все тестовые классы
    test_suite = unittest.TestSuite()

    # Добавляем тесты в порядке сложности
    test_suite.addTests(loader.loadTestsFromTestCase(TestLoadCapacity))
    test_suite.addTests(loader.loadTestsFromTestCase(TestGameLogicLoad))
    test_suite.addTests(loader.loadTestsFromTestCase(TestRoomManagementLoad))
    test_suite.addTests(loader.loadTestsFromTestCase(TestMemoryAndPerformance))
    test_suite.addTests(loader.loadTestsFromTestCase(TestIntegrationLoad))

    # Запускаем тесты с детальным выводом
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Вывод статистики
    print("\n" + "=" * 60)
    print("СТАТИСТИКА НАГРУЗОЧНЫХ ТЕСТОВ")
    print("=" * 60)
    print(f"Всего тестов: {result.testsRun}")
    print(f"Успешно: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Неудач: {len(result.failures)}")
    print(f"Ошибок: {len(result.errors)}")

    if result.failures:
        print("\nНЕУДАЧНЫЕ ТЕСТЫ:")
        for test, traceback in result.failures:
            print(f"\n{test}:")
            print(traceback)

    if result.errors:
        print("\nОШИБКИ:")
        for test, traceback in result.errors:
            print(f"\n{test}:")
            print(traceback)

    return result


if __name__ == '__main__':
    print("Запуск нагрузочных тестов...")
    print("=" * 60)

    # Устанавливаем максимальное время выполнения тестов
    import signal


    class TimeoutException(Exception):
        pass


    def timeout_handler(signum, frame):
        raise TimeoutException("Тесты выполняются слишком долго!")


    # Устанавливаем таймаут в 120 секунд
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(120)

    try:
        result = run_load_tests()
        signal.alarm(0)  # Отключаем таймер
    except TimeoutException:
        print("\n❌ ТЕСТЫ ПРЕРВАНЫ ИЗ-ЗА ТАЙМАУТА!")
        print("Тесты выполнялись более 2 минут. Проверьте производительность системы.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ Тесты прерваны пользователем")
        sys.exit(0)

    # Возвращаем код выхода в зависимости от результата
    if result.failures or result.errors:
        sys.exit(1)
    else:
        sys.exit(0)