"""
Hand Gesture Recognizer Module
Detects hand joints, finger positions, pinch gestures, and rotation
"""

import cv2
import numpy as np
from collections import deque
import math

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False
    print("Warning: MediaPipe not installed. Install with: pip install mediapipe")


class HandGestureRecognizer:
    """Recognizes hand gestures and joint positions using MediaPipe"""
    
    # Hand landmark indices
    WRIST = 0
    THUMB_TIP = 4
    INDEX_TIP = 8
    MIDDLE_TIP = 12
    RING_TIP = 16
    PINKY_TIP = 20
    
    INDEX_MCP = 5      # Index finger base
    INDEX_PIP = 6      # Index finger middle
    THUMB_IP = 3       # Thumb middle
    
    def __init__(self, min_detection_confidence=0.5, max_hands=2):
        self.min_detection_confidence = min_detection_confidence
        self.max_hands = max_hands
        self.rotation_history = deque(maxlen=30)  # Store rotation angles
        self.pinch_position_history = deque(maxlen=50)  # Track pinch point movement
        self.circular_motion_center = None  # Center of circular motion
        self.circular_motion_count = 0  # Count of completed circles
        self.hand_detector = None
        self.drawing_utils = None
        
        if MEDIAPIPE_AVAILABLE:
            self._init_mediapipe()
    
    def _init_mediapipe(self):
        """Initialize MediaPipe hand detection"""
        try:
            print(f"[HandGestureRecognizer] Attempting to initialize MediaPipe")
            import mediapipe as mp
            
            # 尝试新API (>= 0.8.9)
            try:
                print(f"[HandGestureRecognizer] Trying new API...")
                from mediapipe.tasks import python
                from mediapipe.tasks.python import vision
                print(f"[HandGestureRecognizer] New API available")
                # 新API的实现会更复杂，暂时跳过
                raise AttributeError("Using fallback to old API")
            except (ImportError, AttributeError):
                # 回到旧API (< 0.8.9)
                print(f"[HandGestureRecognizer] Trying old API...")
                mp_hands = mp.solutions.hands
                mp_drawing = mp.solutions.drawing_utils
                
                self.hand_detector = mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=self.max_hands,
                    min_detection_confidence=self.min_detection_confidence,
                    min_tracking_confidence=0.5
                )
                self.drawing_utils = mp_drawing
                print(f"[HandGestureRecognizer] Old API initialized successfully")
                return
            
        except Exception as e:
            print(f"[HandGestureRecognizer] Error initializing MediaPipe: {e}")
            import traceback
            traceback.print_exc()
            self.hand_detector = None
            self.drawing_utils = None
            print(f"[HandGestureRecognizer] Hand detection disabled - program will work without pose display")
    
    def process_frame(self, frame):
        """
        Process a frame and detect hand landmarks
        Returns: list of hand data dictionaries
        """
        if not MEDIAPIPE_AVAILABLE or not self.hand_detector:
            return []
        
        try:
            # Convert BGR to RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hand_detector.process(rgb_frame)
            
            hands_data = []
            if results.multi_hand_landmarks and results.multi_handedness:
                for landmarks, handedness in zip(results.multi_hand_landmarks, results.multi_handedness):
                    hand_info = self._extract_hand_data(landmarks, frame, handedness)
                    hands_data.append(hand_info)
            
            return hands_data
        except Exception as e:
            print(f"Error processing frame: {e}")
            return []
    
    def _extract_hand_data(self, landmarks, frame, handedness):
        """Extract useful information from hand landmarks"""
        h, w, c = frame.shape
        
        # Convert landmarks to normalized coordinates
        joints = []
        for lm in landmarks.landmark:
            joints.append({
                'x': lm.x * w,
                'y': lm.y * h,
                'z': lm.z,
                'nx': lm.x,  # normalized x
                'ny': lm.y   # normalized y
            })
        
        hand_data = {
            'handedness': handedness.classification[0].label,
            'confidence': handedness.classification[0].score,
            'joints': joints,
            'pinch_state': self._detect_pinch(joints),
            'index_extended': self._is_index_extended(joints),
            'rotation_angle': self._calculate_rotation_angle(joints),
            'rotation_count': self._calculate_rotation_count(joints),
            'thumb_index_distance': self._calculate_distance(joints[self.THUMB_TIP], joints[self.INDEX_TIP]),
            'circular_motion': self._detect_circular_motion(joints)
        }
        
        return hand_data
    
    def _detect_pinch(self, joints):
        """
        Detect if thumb and index finger are pinched together
        Returns: {is_pinched: bool, distance: float}
        """
        thumb_tip = joints[self.THUMB_TIP]
        index_tip = joints[self.INDEX_TIP]
        
        distance = self._calculate_distance(thumb_tip, index_tip)
        # Pinch threshold: 125像素 - 根据实际测试数据调整
        is_pinched = distance < 125
        
        return {
            'is_pinched': is_pinched,
            'distance': distance,
            'pinch_strength': max(0, 1 - (distance / 150))  # 0-1 scale
        }
    
    def _is_index_extended(self, joints):
        """
        Check if index finger is extended (pointing out)
        Returns: {extended: bool, extension_level: float}
        """
        # Get finger positions
        index_tip = joints[self.INDEX_TIP]
        index_pip = joints[self.INDEX_PIP]
        index_mcp = joints[self.INDEX_MCP]
        
        wrist = joints[self.WRIST]
        middle_tip = joints[self.MIDDLE_TIP]
        
        # Calculate extension by comparing index tip distance from wrist vs other fingers
        index_wrist_dist = self._calculate_distance(index_tip, wrist)
        middle_wrist_dist = self._calculate_distance(middle_tip, wrist)
        
        # Index is extended if it's significantly further from wrist than middle finger
        extension_ratio = index_wrist_dist / (middle_wrist_dist + 0.001)
        is_extended = extension_ratio > 1.1  # 10% more extended
        
        # Calculate extension level (0-1)
        extension_level = min(1.0, max(0, extension_ratio - 0.9) / 0.5)
        
        # Also check if index is more vertical (pointing up)
        index_vec = np.array([index_tip['x'] - index_mcp['x'], 
                             index_tip['y'] - index_mcp['y']])
        magnitude = np.linalg.norm(index_vec) + 0.001
        
        return {
            'extended': is_extended,
            'extension_level': extension_level,
            'pointing_up': index_tip['y'] < index_mcp['y'],  # y decreases going up
            'confidence': extension_level
        }
    
    def _calculate_rotation_angle(self, joints):
        """
        Calculate hand rotation angle based on palm orientation
        Returns angle in degrees (-180 to 180)
        """
        try:
            # Use wrist and middle finger tip to determine hand rotation
            wrist = joints[self.WRIST]
            middle_tip = joints[self.MIDDLE_TIP]
            index_mcp = joints[self.INDEX_MCP]
            pinky_mcp = joints[self.PINKY_TIP]
            
            # Vector from wrist to middle finger (palm orientation)
            palm_vec = np.array([middle_tip['x'] - wrist['x'], 
                                middle_tip['y'] - wrist['y']])
            
            # Vector from index to pinky (hand width)
            width_vec = np.array([pinky_mcp['x'] - index_mcp['x'], 
                                 pinky_mcp['y'] - index_mcp['y']])
            
            # Calculate angle from vertical
            angle = math.atan2(palm_vec[0], -palm_vec[1]) * 180 / math.pi
            
            return angle
        except Exception as e:
            print(f"Error calculating rotation angle: {e}")
            return 0
    
    def _calculate_rotation_count(self, joints):
        """
        Calculate how many full rotations (360 degree turns) the hand has made
        Returns: {rotations: float, current_angle: float}
        """
        current_angle = self._calculate_rotation_angle(joints)
        self.rotation_history.append(current_angle)
        
        if len(self.rotation_history) < 5:
            return {'rotations': 0, 'current_angle': current_angle}
        
        # Detect rotation crossings (from 170° to -170° or vice versa)
        rotation_count = 0
        angles = list(self.rotation_history)
        
        for i in range(1, len(angles)):
            prev_angle = angles[i-1]
            curr_angle = angles[i]
            
            # Detect crossing of ±180 boundary
            diff = curr_angle - prev_angle
            
            # If jump is large, we've crossed the boundary
            if abs(diff) > 90:
                if diff > 0:
                    rotation_count -= 0.5  # Rotating forward
                else:
                    rotation_count += 0.5  # Rotating backward
        
        return {
            'rotations': rotation_count / 2,  # Each crossing is 0.5 rotation
            'current_angle': current_angle,
            'angle_history': list(angles[-5:])  # Last 5 angles
        }
    
    def _calculate_distance(self, point1, point2):
        """Calculate Euclidean distance between two points"""
        dx = point1['x'] - point2['x']
        dy = point1['y'] - point2['y']
        return math.sqrt(dx*dx + dy*dy)
    
    def _detect_circular_motion(self, joints):
        """
        Detect circular motion of pinched fingers around a center point
        Similar to wiping motion with alcohol
        Returns: {is_circular: bool, motion_count: float, center: (x,y), radius: float}
        """
        thumb_tip = joints[self.THUMB_TIP]
        index_tip = joints[self.INDEX_TIP]
        
        # Calculate midpoint between thumb and index (pinch point)
        pinch_point = {
            'x': (thumb_tip['x'] + index_tip['x']) / 2,
            'y': (thumb_tip['y'] + index_tip['y']) / 2
        }
        
        # Add to history
        self.pinch_position_history.append(pinch_point)
        
        # Need enough history to detect motion
        if len(self.pinch_position_history) < 10:
            return {
                'is_circular': False,
                'motion_count': 0,
                'center': None,
                'radius': 0,
                'current_angle': 0,
                'confidence': 0
            }
        
        try:
            # Calculate the center of circular motion (center of mass of recent positions)
            positions = list(self.pinch_position_history)
            center_x = sum(p['x'] for p in positions) / len(positions)
            center_y = sum(p['y'] for p in positions) / len(positions)
            center = (center_x, center_y)
            
            # Calculate radius (average distance from center)
            distances = [self._calculate_distance(p, {'x': center_x, 'y': center_y}) 
                        for p in positions]
            avg_radius = sum(distances) / len(distances)
            
            # Check if motion is circular (variance should be relatively consistent)
            if avg_radius < 10:  # Too small, not circular motion
                return {
                    'is_circular': False,
                    'motion_count': 0,
                    'center': center,
                    'radius': avg_radius,
                    'current_angle': 0,
                    'confidence': 0
                }
            
            # Calculate radius variance (consistency check)
            variance = sum((d - avg_radius)**2 for d in distances) / len(distances)
            radius_std = math.sqrt(variance)
            consistency = max(0, 1 - (radius_std / (avg_radius + 0.001)))
            
            # Detect if motion is circular by checking angle changes
            angles = []
            for p in positions:
                dx = p['x'] - center_x
                dy = p['y'] - center_y
                angle = math.atan2(dy, dx) * 180 / math.pi
                angles.append(angle)
            
            # Count complete circles by detecting angle wraparound
            circle_count = self._count_circles(angles)
            
            # Current angle
            current_angle = angles[-1] if angles else 0
            
            # Consider it circular if radius is consistent and motion is smooth
            is_circular = consistency > 0.5
            
            return {
                'is_circular': is_circular,
                'motion_count': circle_count,
                'center': center,
                'radius': avg_radius,
                'current_angle': current_angle,
                'confidence': consistency,
                'radius_consistency': consistency
            }
        
        except Exception as e:
            print(f"Error detecting circular motion: {e}")
            return {
                'is_circular': False,
                'motion_count': 0,
                'center': None,
                'radius': 0,
                'current_angle': 0,
                'confidence': 0
            }
    
    def _count_circles(self, angles):
        """
        Count number of complete circles based on angle history
        Returns: float (0 = no circles, 0.5 = half circle, 1.0 = one complete circle, etc.)
        """
        if len(angles) < 5:
            return 0
        
        circle_count = 0
        crossings = 0
        
        for i in range(1, len(angles)):
            prev_angle = angles[i-1]
            curr_angle = angles[i]
            
            # Detect crossing of ±180 boundary
            diff = curr_angle - prev_angle
            
            # Large jumps indicate crossing the boundary
            if abs(diff) > 90:
                crossings += 1
        
        # Each complete circle has 2 crossings (crossing 180, then crossing -180)
        circle_count = crossings / 2.0
        
        return circle_count
    
    def draw_hand_landmarks(self, frame, hand_data):
        """
        Draw hand landmarks on frame
        Returns: annotated frame
        """
        if not MEDIAPIPE_AVAILABLE or not self.drawing_utils:
            return frame
        
        try:
            # Convert joint data back to MediaPipe format for drawing
            h, w, c = frame.shape
            
            for joint in hand_data['joints']:
                x = int(joint['x'])
                y = int(joint['y'])
                cv2.circle(frame, (x, y), 3, (0, 255, 0), -1)
            
            # Draw connections between joints (simplified)
            connections = [
                (0, 1), (1, 2), (2, 3), (3, 4),      # Thumb
                (0, 5), (5, 6), (6, 7), (7, 8),      # Index
                (0, 9), (9, 10), (10, 11), (11, 12), # Middle
                (0, 13), (13, 14), (14, 15), (15, 16), # Ring
                (0, 17), (17, 18), (18, 19), (19, 20) # Pinky
            ]
            
            for start_idx, end_idx in connections:
                start = hand_data['joints'][start_idx]
                end = hand_data['joints'][end_idx]
                cv2.line(frame, (int(start['x']), int(start['y'])), 
                        (int(end['x']), int(end['y'])), (255, 0, 0), 2)
            
            # Draw pinch indicator
            if hand_data['pinch_state']['is_pinched']:
                thumb_tip = hand_data['joints'][self.THUMB_TIP]
                index_tip = hand_data['joints'][self.INDEX_TIP]
                cv2.line(frame, (int(thumb_tip['x']), int(thumb_tip['y'])), 
                        (int(index_tip['x']), int(index_tip['y'])), (0, 0, 255), 3)
            
            # Draw circular motion center and trajectory
            circular = hand_data['circular_motion']
            if circular['center'] and circular['is_circular']:
                center = (int(circular['center'][0]), int(circular['center'][1]))
                radius = int(circular['radius'])
                
                # Draw center point
                cv2.circle(frame, center, 5, (255, 0, 255), -1)
                
                # Draw circular boundary
                cv2.circle(frame, center, radius, (255, 0, 255), 2)
                
                # Draw motion history as trajectory
                if len(self.pinch_position_history) > 1:
                    positions = list(self.pinch_position_history)
                    for i in range(1, len(positions)):
                        p1 = (int(positions[i-1]['x']), int(positions[i-1]['y']))
                        p2 = (int(positions[i]['x']), int(positions[i]['y']))
                        cv2.line(frame, p1, p2, (0, 255, 255), 1)
        
        except Exception as e:
            print(f"Error drawing landmarks: {e}")
        
        return frame
    
    def get_gesture_summary(self, hand_data):
        """Get a human-readable summary of hand gesture"""
        summary = []
        
        # Handedness
        summary.append(f"Hand: {hand_data['handedness']}")
        
        # Pinch state
        if hand_data['pinch_state']['is_pinched']:
            summary.append("🤏 Pinching")
            
            # Check for circular wiping motion
            circular = hand_data['circular_motion']
            if circular['is_circular']:
                motion_count = circular['motion_count']
                if motion_count > 0.3:
                    summary.append(f"♻️ Wiping: {motion_count:.1f} circles")
        
        # Index finger state
        if hand_data['index_extended']['extended']:
            summary.append("☝️ Index pointing")
        
        return " | ".join(summary)


if __name__ == "__main__":
    # Test the recognizer
    if not MEDIAPIPE_AVAILABLE:
        print("MediaPipe not available. Install with: pip install mediapipe")
    else:
        recognizer = HandGestureRecognizer()
        cap = cv2.VideoCapture(0)
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            hands_data = recognizer.process_frame(frame)
            
            for hand_data in hands_data:
                frame = recognizer.draw_hand_landmarks(frame, hand_data)
                summary = recognizer.get_gesture_summary(hand_data)
                cv2.putText(frame, summary, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                           0.7, (0, 255, 0), 2)
            
            cv2.imshow('Hand Gesture Recognizer', frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
