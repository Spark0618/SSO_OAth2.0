import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from sqlalchemy import text
from models import db, User, Student, Course, Enrollment, Assignment, AssignmentSubmission

class ProgressTracker:
    """学生学习进度跟踪器"""
    
    def __init__(self, db_session):
        """
        初始化进度跟踪器
        
        Args:
            db_session: 数据库会话
        """
        self.db = db_session
    
    def get_student_course_progress(self, student_id: int, course_id: int) -> Dict[str, Any]:
        """
        获取学生在特定课程中的学习进度
        
        Args:
            student_id: 学生ID
            course_id: 课程ID
            
        Returns:
            包含课程进度信息的字典
        """
        try:
            # 获取课程信息
            course = self.db.query(Course).filter(Course.id == course_id).first()
            if not course:
                return {"success": False, "message": "Course not found"}
            
            # 获取学生选课信息
            enrollment = self.db.query(Enrollment).filter(
                Enrollment.student_id == student_id,
                Enrollment.course_id == course_id
            ).first()
            
            if not enrollment:
                return {"success": False, "message": "Student not enrolled in this course"}
            
            # 获取课程所有作业
            assignments = self.db.query(Assignment).filter(
                Assignment.course_id == course_id
            ).all()
            
            # 获取学生已提交的作业
            submissions = self.db.query(AssignmentSubmission).join(Assignment).filter(
                AssignmentSubmission.student_id == student_id,
                Assignment.course_id == course_id
            ).all()
            
            # 计算作业完成情况
            total_assignments = len(assignments)
            submitted_assignments = len(submissions)
            graded_assignments = sum(1 for s in submissions if s.grade is not None)
            
            # 计算平均分
            total_score = sum(s.grade for s in submissions if s.grade is not None)
            avg_score = total_score / graded_assignments if graded_assignments > 0 else 0
            
            # 计算完成率
            completion_rate = (submitted_assignments / total_assignments) * 100 if total_assignments > 0 else 0
            
            # 获取作业详情
            assignment_details = []
            for assignment in assignments:
                submission = next((s for s in submissions if s.assignment_id == assignment.id), None)
                
                assignment_details.append({
                    "assignment_id": assignment.id,
                    "title": assignment.title,
                    "description": assignment.description,
                    "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
                    "max_score": assignment.max_score,
                    "submitted": submission is not None,
                    "submission_date": submission.submission_date.isoformat() if submission and submission.submission_date else None,
                    "grade": submission.grade if submission else None,
                    "feedback": submission.feedback if submission else None,
                    "status": self._get_assignment_status(assignment, submission)
                })
            
            return {
                "success": True,
                "course": {
                    "id": course.id,
                    "code": course.code,
                    "title": course.title,
                    "description": course.description
                },
                "enrollment": {
                    "enrollment_date": enrollment.enrollment_date.isoformat() if enrollment.enrollment_date else None,
                    "grade": enrollment.grade
                },
                "progress": {
                    "total_assignments": total_assignments,
                    "submitted_assignments": submitted_assignments,
                    "graded_assignments": graded_assignments,
                    "completion_rate": round(completion_rate, 2),
                    "average_score": round(avg_score, 2)
                },
                "assignments": assignment_details
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_student_overall_progress(self, student_id: int) -> Dict[str, Any]:
        """
        获取学生整体学习进度
        
        Args:
            student_id: 学生ID
            
        Returns:
            包含整体进度信息的字典
        """
        try:
            # 获取学生信息
            student = self.db.query(Student).filter(Student.id == student_id).first()
            if not student:
                return {"success": False, "message": "Student not found"}
            
            # 获取学生所有选课
            enrollments = self.db.query(Enrollment).filter(
                Enrollment.student_id == student_id
            ).all()
            
            # 获取所有课程进度
            course_progresses = []
            total_assignments = 0
            total_submitted = 0
            total_graded = 0
            total_score = 0
            
            for enrollment in enrollments:
                course_progress = self.get_student_course_progress(student_id, enrollment.course_id)
                if course_progress["success"]:
                    course_progresses.append(course_progress)
                    progress = course_progress["progress"]
                    total_assignments += progress["total_assignments"]
                    total_submitted += progress["submitted_assignments"]
                    total_graded += progress["graded_assignments"]
                    total_score += progress["average_score"] * progress["graded_assignments"] if progress["graded_assignments"] > 0 else 0
            
            # 计算整体统计
            overall_completion_rate = (total_submitted / total_assignments) * 100 if total_assignments > 0 else 0
            overall_avg_score = total_score / total_graded if total_graded > 0 else 0
            
            # 获取最近活动
            recent_activities = self._get_recent_student_activities(student_id, limit=10)
            
            return {
                "success": True,
                "student": {
                    "id": student.id,
                    "name": student.name,
                    "student_no": student.student_no
                },
                "overall_progress": {
                    "total_courses": len(enrollments),
                    "total_assignments": total_assignments,
                    "total_submitted": total_submitted,
                    "total_graded": total_graded,
                    "overall_completion_rate": round(overall_completion_rate, 2),
                    "overall_average_score": round(overall_avg_score, 2)
                },
                "course_progresses": course_progresses,
                "recent_activities": recent_activities
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_course_statistics(self, course_id: int) -> Dict[str, Any]:
        """
        获取课程统计信息
        
        Args:
            course_id: 课程ID
            
        Returns:
            包含课程统计信息的字典
        """
        try:
            # 获取课程信息
            course = self.db.query(Course).filter(Course.id == course_id).first()
            if not course:
                return {"success": False, "message": "Course not found"}
            
            # 获取选课学生数
            enrollment_count = self.db.query(Enrollment).filter(
                Enrollment.course_id == course_id
            ).count()
            
            # 获取课程所有作业
            assignments = self.db.query(Assignment).filter(
                Assignment.course_id == course_id
            ).all()
            
            # 获取所有提交
            submissions = self.db.query(AssignmentSubmission).join(Assignment).filter(
                Assignment.course_id == course_id
            ).all()
            
            # 计算作业统计
            assignment_stats = []
            for assignment in assignments:
                assignment_submissions = [s for s in submissions if s.assignment_id == assignment.id]
                submitted_count = len(assignment_submissions)
                graded_count = sum(1 for s in assignment_submissions if s.grade is not None)
                
                # 计算平均分和分数分布
                grades = [s.grade for s in assignment_submissions if s.grade is not None]
                avg_score = sum(grades) / len(grades) if grades else 0
                
                # 计算分数分布
                score_distribution = self._calculate_score_distribution(grades, assignment.max_score)
                
                assignment_stats.append({
                    "assignment_id": assignment.id,
                    "title": assignment.title,
                    "due_date": assignment.due_date.isoformat() if assignment.due_date else None,
                    "max_score": assignment.max_score,
                    "enrolled_students": enrollment_count,
                    "submitted_count": submitted_count,
                    "graded_count": graded_count,
                    "submission_rate": round((submitted_count / enrollment_count) * 100, 2) if enrollment_count > 0 else 0,
                    "average_score": round(avg_score, 2),
                    "score_distribution": score_distribution
                })
            
            # 计算整体课程统计
            total_submissions = len(submissions)
            total_graded = sum(1 for s in submissions if s.grade is not None)
            all_grades = [s.grade for s in submissions if s.grade is not None]
            overall_avg_score = sum(all_grades) / len(all_grades) if all_grades else 0
            overall_score_distribution = self._calculate_score_distribution(all_grades, 100)
            
            # 获取学生进度分布
            progress_distribution = self._calculate_progress_distribution(course_id)
            
            return {
                "success": True,
                "course": {
                    "id": course.id,
                    "code": course.code,
                    "title": course.title,
                    "description": course.description
                },
                "statistics": {
                    "enrolled_students": enrollment_count,
                    "total_assignments": len(assignments),
                    "total_submissions": total_submissions,
                    "total_graded": total_graded,
                    "overall_submission_rate": round((total_submissions / (len(assignments) * enrollment_count)) * 100, 2) if enrollment_count > 0 and len(assignments) > 0 else 0,
                    "overall_average_score": round(overall_avg_score, 2),
                    "overall_score_distribution": overall_score_distribution,
                    "progress_distribution": progress_distribution
                },
                "assignment_statistics": assignment_stats
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_student_performance_trends(self, student_id: int, days: int = 30) -> Dict[str, Any]:
        """
        获取学生表现趋势
        
        Args:
            student_id: 学生ID
            days: 统计天数
            
        Returns:
            包含表现趋势的字典
        """
        try:
            # 获取学生信息
            student = self.db.query(Student).filter(Student.id == student_id).first()
            if not student:
                return {"success": False, "message": "Student not found"}
            
            # 计算时间范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 获取时间范围内的提交记录
            submissions = self.db.query(AssignmentSubmission).join(Assignment).filter(
                AssignmentSubmission.student_id == student_id,
                AssignmentSubmission.submission_date >= start_date,
                AssignmentSubmission.submission_date <= end_date
            ).order_by(AssignmentSubmission.submission_date).all()
            
            # 按日期分组统计
            daily_data = {}
            for submission in submissions:
                date_str = submission.submission_date.strftime('%Y-%m-%d')
                if date_str not in daily_data:
                    daily_data[date_str] = {
                        "date": date_str,
                        "submissions": 0,
                        "total_score": 0,
                        "graded_count": 0
                    }
                
                daily_data[date_str]["submissions"] += 1
                if submission.grade is not None:
                    daily_data[date_str]["total_score"] += submission.grade
                    daily_data[date_str]["graded_count"] += 1
            
            # 计算每日平均分
            daily_trends = []
            for date_str, data in sorted(daily_data.items()):
                avg_score = data["total_score"] / data["graded_count"] if data["graded_count"] > 0 else 0
                daily_trends.append({
                    "date": date_str,
                    "submissions": data["submissions"],
                    "average_score": round(avg_score, 2)
                })
            
            # 计算整体趋势
            total_submissions = len(submissions)
            graded_submissions = [s for s in submissions if s.grade is not None]
            total_score = sum(s.grade for s in graded_submissions)
            overall_avg_score = total_score / len(graded_submissions) if graded_submissions else 0
            
            return {
                "success": True,
                "student": {
                    "id": student.id,
                    "name": student.name,
                    "student_no": student.student_no
                },
                "period": {
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d'),
                    "days": days
                },
                "summary": {
                    "total_submissions": total_submissions,
                    "graded_submissions": len(graded_submissions),
                    "overall_average_score": round(overall_avg_score, 2)
                },
                "daily_trends": daily_trends
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def get_course_performance_trends(self, course_id: int, days: int = 30) -> Dict[str, Any]:
        """
        获取课程表现趋势
        
        Args:
            course_id: 课程ID
            days: 统计天数
            
        Returns:
            包含课程表现趋势的字典
        """
        try:
            # 获取课程信息
            course = self.db.query(Course).filter(Course.id == course_id).first()
            if not course:
                return {"success": False, "message": "Course not found"}
            
            # 计算时间范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # 获取时间范围内的提交记录
            submissions = self.db.query(AssignmentSubmission).join(Assignment).filter(
                Assignment.course_id == course_id,
                AssignmentSubmission.submission_date >= start_date,
                AssignmentSubmission.submission_date <= end_date
            ).order_by(AssignmentSubmission.submission_date).all()
            
            # 按日期分组统计
            daily_data = {}
            for submission in submissions:
                date_str = submission.submission_date.strftime('%Y-%m-%d')
                if date_str not in daily_data:
                    daily_data[date_str] = {
                        "date": date_str,
                        "submissions": 0,
                        "total_score": 0,
                        "graded_count": 0
                    }
                
                daily_data[date_str]["submissions"] += 1
                if submission.grade is not None:
                    daily_data[date_str]["total_score"] += submission.grade
                    daily_data[date_str]["graded_count"] += 1
            
            # 计算每日平均分
            daily_trends = []
            for date_str, data in sorted(daily_data.items()):
                avg_score = data["total_score"] / data["graded_count"] if data["graded_count"] > 0 else 0
                daily_trends.append({
                    "date": date_str,
                    "submissions": data["submissions"],
                    "average_score": round(avg_score, 2)
                })
            
            # 计算整体趋势
            total_submissions = len(submissions)
            graded_submissions = [s for s in submissions if s.grade is not None]
            total_score = sum(s.grade for s in graded_submissions)
            overall_avg_score = total_score / len(graded_submissions) if graded_submissions else 0
            
            return {
                "success": True,
                "course": {
                    "id": course.id,
                    "code": course.code,
                    "title": course.title
                },
                "period": {
                    "start_date": start_date.strftime('%Y-%m-%d'),
                    "end_date": end_date.strftime('%Y-%m-%d'),
                    "days": days
                },
                "summary": {
                    "total_submissions": total_submissions,
                    "graded_submissions": len(graded_submissions),
                    "overall_average_score": round(overall_avg_score, 2)
                },
                "daily_trends": daily_trends
            }
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def _get_assignment_status(self, assignment: Assignment, submission: Optional[AssignmentSubmission]) -> str:
        """获取作业状态"""
        if not submission:
            if assignment.due_date and datetime.now() > assignment.due_date:
                return "overdue"
            return "not_submitted"
        
        if submission.grade is not None:
            return "graded"
        
        if assignment.due_date and submission.submission_date > assignment.due_date:
            return "late_submitted"
        
        return "submitted"
    
    def _get_recent_student_activities(self, student_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """获取学生最近活动"""
        try:
            # 获取最近提交的作业
            submissions = self.db.query(AssignmentSubmission).join(Assignment).join(Course).filter(
                AssignmentSubmission.student_id == student_id
            ).order_by(AssignmentSubmission.submission_date.desc()).limit(limit).all()
            
            activities = []
            for submission in submissions:
                activities.append({
                    "type": "assignment_submission",
                    "date": submission.submission_date.isoformat(),
                    "details": {
                        "assignment_id": submission.assignment_id,
                        "assignment_title": submission.assignment.title,
                        "course_code": submission.assignment.course.code,
                        "course_title": submission.assignment.course.title,
                        "grade": submission.grade,
                        "feedback": submission.feedback
                    }
                })
            
            return activities
        except Exception as e:
            return []
    
    def _calculate_score_distribution(self, grades: List[float], max_score: float) -> Dict[str, int]:
        """计算分数分布"""
        distribution = {
            "90-100": 0,
            "80-89": 0,
            "70-79": 0,
            "60-69": 0,
            "below_60": 0
        }
        
        for grade in grades:
            percentage = (grade / max_score) * 100 if max_score > 0 else 0
            if percentage >= 90:
                distribution["90-100"] += 1
            elif percentage >= 80:
                distribution["80-89"] += 1
            elif percentage >= 70:
                distribution["70-79"] += 1
            elif percentage >= 60:
                distribution["60-69"] += 1
            else:
                distribution["below_60"] += 1
        
        return distribution
    
    def _calculate_progress_distribution(self, course_id: int) -> Dict[str, int]:
        """计算学生进度分布"""
        try:
            # 获取课程所有学生
            enrollments = self.db.query(Enrollment).filter(
                Enrollment.course_id == course_id
            ).all()
            
            # 获取课程所有作业
            assignments = self.db.query(Assignment).filter(
                Assignment.course_id == course_id
            ).all()
            
            if not assignments:
                return {"no_assignments": len(enrollments)}
            
            total_assignments = len(assignments)
            distribution = {
                "0-25%": 0,
                "26-50%": 0,
                "51-75%": 0,
                "76-99%": 0,
                "100%": 0
            }
            
            for enrollment in enrollments:
                # 获取学生提交的作业数
                submitted_count = self.db.query(AssignmentSubmission).join(Assignment).filter(
                    AssignmentSubmission.student_id == enrollment.student_id,
                    Assignment.course_id == course_id
                ).count()
                
                # 计算完成率
                completion_rate = (submitted_count / total_assignments) * 100 if total_assignments > 0 else 0
                
                # 分类
                if completion_rate == 100:
                    distribution["100%"] += 1
                elif completion_rate >= 76:
                    distribution["76-99%"] += 1
                elif completion_rate >= 51:
                    distribution["51-75%"] += 1
                elif completion_rate >= 26:
                    distribution["26-50%"] += 1
                else:
                    distribution["0-25%"] += 1
            
            return distribution
        except Exception as e:
            return {}