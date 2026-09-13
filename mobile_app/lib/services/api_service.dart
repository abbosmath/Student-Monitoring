import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  // Live Render production host
  static String baseUrl = "https://mobile-student-monitoring.onrender.com/api";

  static Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString("api_token");
  }

  static Future<void> saveToken(String token, String role) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString("api_token", token);
    await prefs.setString("user_role", role);
  }

  static Future<void> clearAuth() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove("api_token");
    await prefs.remove("user_role");
  }

  static Future<String?> getRole() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString("user_role");
  }

  static Future<Map<String, String>> _getHeaders() async {
    final token = await getToken();
    return {
      "Content-Type": "application/json",
      if (token != null) "Authorization": "Bearer $token",
    };
  }

  static Map<String, dynamic> _parseResponse(http.Response res) {
    try {
      final decoded = jsonDecode(res.body);
      if (decoded is Map<String, dynamic>) return decoded;
      return {"data": decoded};
    } catch (_) {
      if (res.body.contains("rate limited") || res.statusCode == 429) {
        return {"error": "Railway Server Rate Limited / Subscription Past Due."};
      } else if (res.statusCode == 502 || res.body.contains("Bad Gateway")) {
        return {"error": "Railway Server 502 Bad Gateway."};
      }
      return {"error": "Server response: ${res.body}"};
    }
  }

  // --- AUTHENTICATION ---
  static Future<Map<String, dynamic>> loginTeacher(String username, String password) async {
    try {
      final url = Uri.parse("$baseUrl/auth/login/teacher/");
      final res = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"username": username, "password": password}),
      );
      final data = _parseResponse(res);
      if (res.statusCode == 200 && data.containsKey("token")) {
        await saveToken(data["token"], "teacher");
      }
      return data;
    } catch (e) {
      return {"error": "Connection error: $e"};
    }
  }

  static Future<Map<String, dynamic>> loginStudent(String identifier) async {
    try {
      final url = Uri.parse("$baseUrl/auth/login/student/");
      final res = await http.post(
        url,
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"identifier": identifier}),
      );
      final data = _parseResponse(res);
      if (res.statusCode == 200 && data.containsKey("token")) {
        await saveToken(data["token"], "student");
      }
      return data;
    } catch (e) {
      return {"error": "Connection error: $e"};
    }
  }

  static Future<Map<String, dynamic>> getMe() async {
    final url = Uri.parse("$baseUrl/auth/me/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    return jsonDecode(res.body);
  }

  // --- TEACHER API ---
  static Future<List<dynamic>> getTeacherGroups() async {
    final url = Uri.parse("$baseUrl/teacher/groups/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    if (res.statusCode == 200) {
      return jsonDecode(res.body)["groups"] ?? [];
    }
    return [];
  }

  static Future<Map<String, dynamic>> createGroup(String name, String subject, List<Map<String, dynamic>> schedules) async {
    final url = Uri.parse("$baseUrl/teacher/groups/");
    final headers = await _getHeaders();
    final res = await http.post(url, headers: headers, body: jsonEncode({
      "name": name,
      "subject": subject,
      "schedules": schedules,
    }));
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> getGroupDetail(int groupId) async {
    final url = Uri.parse("$baseUrl/teacher/groups/$groupId/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> addStudentToGroup(int groupId, int studentId) async {
    final url = Uri.parse("$baseUrl/teacher/groups/$groupId/add-student/");
    final headers = await _getHeaders();
    final res = await http.post(url, headers: headers, body: jsonEncode({"student_id": studentId}));
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> removeStudentFromGroup(int groupId, int studentId) async {
    final url = Uri.parse("$baseUrl/teacher/groups/$groupId/remove-student/$studentId/");
    final headers = await _getHeaders();
    final res = await http.delete(url, headers: headers);
    return jsonDecode(res.body);
  }

  static Future<List<dynamic>> getTeacherStudents() async {
    final url = Uri.parse("$baseUrl/teacher/students/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    if (res.statusCode == 200) {
      return jsonDecode(res.body)["students"] ?? [];
    }
    return [];
  }

  static Future<Map<String, dynamic>> createStudent(String fullName, String parentName, String telegramId, String phone, int? groupId) async {
    final url = Uri.parse("$baseUrl/teacher/students/");
    final headers = await _getHeaders();
    final res = await http.post(url, headers: headers, body: jsonEncode({
      "full_name": fullName,
      "parent_name": parentName,
      "telegram_id": telegramId,
      "phone": phone,
      "group_id": groupId,
    }));
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> adjustStudentPoints(int studentId, int points, String action, String comment) async {
    final url = Uri.parse("$baseUrl/teacher/students/$studentId/points/");
    final headers = await _getHeaders();
    final res = await http.post(url, headers: headers, body: jsonEncode({
      "points": points,
      "action": action,
      "comment": comment,
    }));
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> addPayment(int studentId, double amount, String paymentDate, String? nextPaymentDate, String note) async {
    final url = Uri.parse("$baseUrl/teacher/students/$studentId/payment/");
    final headers = await _getHeaders();
    final res = await http.post(url, headers: headers, body: jsonEncode({
      "amount": amount,
      "payment_date": paymentDate,
      "next_payment_date": nextPaymentDate,
      "note": note,
    }));
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> takeAttendance(int groupId, String date, List<Map<String, dynamic>> records) async {
    final url = Uri.parse("$baseUrl/teacher/attendance/$groupId/");
    final headers = await _getHeaders();
    final res = await http.post(url, headers: headers, body: jsonEncode({
      "date": date,
      "records": records,
    }));
    return jsonDecode(res.body);
  }

  static Future<List<dynamic>> getTeacherMarketItems() async {
    final url = Uri.parse("$baseUrl/teacher/market/items/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    if (res.statusCode == 200) {
      return jsonDecode(res.body)["items"] ?? [];
    }
    return [];
  }

  static Future<Map<String, dynamic>> createMarketItem(String title, String itemType, int pointsCost, int quantity, int? discountPercent, String description, String? imageUrl) async {
    final url = Uri.parse("$baseUrl/teacher/market/items/");
    final headers = await _getHeaders();
    final res = await http.post(url, headers: headers, body: jsonEncode({
      "title": title,
      "item_type": itemType,
      "points_cost": pointsCost,
      "quantity": quantity,
      "discount_percent": discountPercent,
      "description": description,
      "image_url": imageUrl,
    }));
    return jsonDecode(res.body);
  }

  static Future<List<dynamic>> getTeacherMarketOrders() async {
    final url = Uri.parse("$baseUrl/teacher/market/orders/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    if (res.statusCode == 200) {
      return jsonDecode(res.body)["orders"] ?? [];
    }
    return [];
  }

  static Future<Map<String, dynamic>> updateOrderStatus(int orderId, String newStatus) async {
    final url = Uri.parse("$baseUrl/teacher/market/orders/");
    final headers = await _getHeaders();
    final res = await http.patch(url, headers: headers, body: jsonEncode({
      "order_id": orderId,
      "status": newStatus,
    }));
    return jsonDecode(res.body);
  }

  static Future<List<dynamic>> getTeacherTests() async {
    final url = Uri.parse("$baseUrl/teacher/tests/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    if (res.statusCode == 200) {
      return jsonDecode(res.body)["tests"] ?? [];
    }
    return [];
  }

  static Future<Map<String, dynamic>> createTest(int groupId, String title, String? deadline, int timeLimitMinutes, List<Map<String, dynamic>> questions) async {
    final url = Uri.parse("$baseUrl/teacher/tests/");
    final headers = await _getHeaders();
    final res = await http.post(url, headers: headers, body: jsonEncode({
      "group_id": groupId,
      "title": title,
      "deadline": deadline,
      "time_limit_minutes": timeLimitMinutes,
      "questions": questions,
    }));
    return jsonDecode(res.body);
  }

  // --- STUDENT API ---
  static Future<Map<String, dynamic>> getStudentDashboard() async {
    final url = Uri.parse("$baseUrl/student/dashboard/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    return jsonDecode(res.body);
  }

  static Future<List<dynamic>> getStudentTests() async {
    final url = Uri.parse("$baseUrl/student/tests/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    if (res.statusCode == 200) {
      return jsonDecode(res.body)["tests"] ?? [];
    }
    return [];
  }

  static Future<Map<String, dynamic>> getStudentTestDetail(int testId) async {
    final url = Uri.parse("$baseUrl/student/tests/$testId/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> submitTest(int testId, Map<String, dynamic> answers) async {
    final url = Uri.parse("$baseUrl/student/tests/$testId/submit/");
    final headers = await _getHeaders();
    final res = await http.post(url, headers: headers, body: jsonEncode({"answers": answers}));
    return jsonDecode(res.body);
  }

  static Future<List<dynamic>> getLeaderboard() async {
    final url = Uri.parse("$baseUrl/student/leaderboard/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    if (res.statusCode == 200) {
      return jsonDecode(res.body)["leaderboards"] ?? [];
    }
    return [];
  }

  static Future<Map<String, dynamic>> getStudentMarketItems() async {
    final url = Uri.parse("$baseUrl/student/market/items/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    return jsonDecode(res.body);
  }

  static Future<Map<String, dynamic>> buyMarketItem(int itemId) async {
    final url = Uri.parse("$baseUrl/student/market/buy/");
    final headers = await _getHeaders();
    final res = await http.post(url, headers: headers, body: jsonEncode({"item_id": itemId}));
    return jsonDecode(res.body);
  }

  static Future<List<dynamic>> getStudentOrders() async {
    final url = Uri.parse("$baseUrl/student/market/orders/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    if (res.statusCode == 200) {
      return jsonDecode(res.body)["orders"] ?? [];
    }
    return [];
  }

  static Future<Map<String, dynamic>> getStudentStats() async {
    final url = Uri.parse("$baseUrl/student/stats/");
    final headers = await _getHeaders();
    final res = await http.get(url, headers: headers);
    return jsonDecode(res.body);
  }
}
