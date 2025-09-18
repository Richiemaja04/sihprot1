import pandas as pd
import random
import collections
import time
import uuid
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import dataclass
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from database.model import OptimizationLog, TimetableVersion
from database.db import get_db_session
from config import settings

logger = logging.getLogger(__name__)

@dataclass
class GAConfig:
    population_size: int = settings.POPULATION_SIZE
    max_generations: int = settings.MAX_GENERATIONS
    mutation_rate: float = settings.MUTATION_RATE
    elitism_rate: float = settings.ELITISM_RATE
    tournament_size: int = settings.TOURNAMENT_SIZE
    parallel_runs: int = settings.MAX_PARALLEL_RUNS

@dataclass
class ClassInfo:
    batch_id: str
    subject_name: str
    subject_type: str
    student_count: int
    credits: int
    hours_per_week: int

@dataclass
class Gene:
    batch_id: str
    subject_name: str
    faculty_id: str
    room_id: str
    day: str
    hour: int
    week_type: str = "all"

class EnhancedTimetableGA:
    def __init__(self, config: GAConfig):
        self.config = config
        self.population = []
        self.fitness_history = []
        self.run_id = str(uuid.uuid4())
        self.timeslots = [(day, hour) for day in settings.DAYS for hour in range(1, settings.HOURS_PER_DAY + 1)]
        
    def prepare_data(self, batches_df: pd.DataFrame, classrooms_df: pd.DataFrame, 
                    faculty_df: pd.DataFrame, subjects_df: pd.DataFrame) -> Dict[str, Any]:
        """Prepare data for GA processing with enhanced structures"""
        
        # Separate rooms by type
        labs = classrooms_df[classrooms_df['Room_Type'] == 'Laboratory'].to_dict('records')
        lecture_halls = classrooms_df[classrooms_df['Room_Type'] != 'Laboratory'].to_dict('records')
        
        # Create faculty-subject mapping with qualifications
        faculty_subject_map = collections.defaultdict(list)
        faculty_workload = {}
        
        for _, row in faculty_df.iterrows():
            subjects = [s.strip() for s in row['subject_name'].split(',')]
            for subject in subjects:
                faculty_subject_map[subject].append(row['Employee ID'])
            faculty_workload[row['Employee ID']] = {
                'max_hours': getattr(row, 'max_hours_per_week', 20),
                'current_hours': 0
            }
        
        # Create classes to schedule with enhanced info
        classes_to_schedule = []
        batch_subject_faculty_map = {}
        
        for _, batch in batches_df.iterrows():
            batch_id = f"{batch['department']}-{batch['level']}-{batch['semester']}"
            subjects = [s.strip() for s in str(batch['subjects']).split(',')]
            
            for subject_name in subjects:
                subject_details = subjects_df[subjects_df['name'] == subject_name]
                if not subject_details.empty:
                    credits = subject_details.iloc[0]['credits']
                    subject_type = subject_details.iloc[0]['type']
                    
                    # Enhanced credit to hours mapping
                    hours_per_week = self._calculate_hours_per_week(credits, subject_type)
                    
                    # Smart faculty assignment based on workload
                    qualified_faculties = faculty_subject_map.get(subject_name, [])
                    if qualified_faculties:
                        # Assign faculty with least current workload
                        best_faculty = min(qualified_faculties, 
                                         key=lambda f: faculty_workload[f]['current_hours'])
                        batch_subject_faculty_map[(batch_id, subject_name)] = best_faculty
                        faculty_workload[best_faculty]['current_hours'] += hours_per_week
                        
                        # Create class sessions
                        for session in range(hours_per_week):
                            classes_to_schedule.append(ClassInfo(
                                batch_id=batch_id,
                                subject_name=subject_name,
                                subject_type=subject_type,
                                student_count=batch['student_count'],
                                credits=credits,
                                hours_per_week=hours_per_week
                            ))
        
        return {
            'labs': labs,
            'lecture_halls': lecture_halls,
            'faculty_subject_map': faculty_subject_map,
            'classes_to_schedule': classes_to_schedule,
            'batch_subject_faculty_map': batch_subject_faculty_map,
            'faculty_workload': faculty_workload
        }
    
    def _calculate_hours_per_week(self, credits: int, subject_type: str) -> int:
        """Enhanced hours per week calculation"""
        if subject_type == 'Lab':
            return min(credits * 2, 4)  # Labs get more hours
        elif credits >= 4:
            return 3
        elif credits == 3:
            return 2
        else:
            return 1
    
    def _create_gene(self, class_info: ClassInfo, used_slots: Dict, data: Dict) -> Optional[Gene]:
        """Create a single gene with enhanced constraint checking"""
        # Get pre-assigned faculty
        faculty_id = data['batch_subject_faculty_map'].get(
            (class_info.batch_id, class_info.subject_name)
        )
        
        if not faculty_id:
            return None
        
        # Select appropriate room
        if class_info.subject_type == 'Lab':
            possible_rooms = [r for r in data['labs'] 
                            if r['Capacity'] >= class_info.student_count]
        else:
            possible_rooms = [r for r in data['lecture_halls'] 
                            if r['Capacity'] >= class_info.student_count]
        
        if not possible_rooms:
            return None
        
        # Smart timeslot selection with preferences
        preferred_slots = self._get_preferred_slots(class_info.subject_type)
        available_slots = []
        
        for timeslot in preferred_slots:
            day, hour = timeslot
            if (timeslot not in used_slots['faculty'].get(faculty_id, set()) and
                timeslot not in used_slots['batch'].get(class_info.batch_id, set())):
                
                # Check room availability
                for room in possible_rooms:
                    if timeslot not in used_slots['room'].get(room['Class_ID'], set()):
                        available_slots.append((timeslot, room))
                        break
        
        if not available_slots:
            return None
        
        # Select best slot-room combination
        timeslot, room = random.choice(available_slots)
        day, hour = timeslot
        
        return Gene(
            batch_id=class_info.batch_id,
            subject_name=class_info.subject_name,
            faculty_id=faculty_id,
            room_id=room['Class_ID'],
            day=day,
            hour=hour
        )
    
    def _get_preferred_slots(self, subject_type: str) -> List[Tuple[str, int]]:
        """Get preferred time slots based on subject type"""
        all_slots = self.timeslots.copy()
        
        if subject_type == 'Lab':
            # Labs prefer afternoon slots
            preferred = [slot for slot in all_slots if slot[1] >= 3]
            return preferred + [slot for slot in all_slots if slot not in preferred]
        else:
            # Theory classes prefer morning slots
            preferred = [slot for slot in all_slots if slot[1] <= 3]
            return preferred + [slot for slot in all_slots if slot not in preferred]
    
    def create_chromosome(self, data: Dict) -> List[Gene]:
        """Create a valid chromosome with enhanced initialization"""
        chromosome = []
        used_slots = {
            'faculty': collections.defaultdict(set),
            'batch': collections.defaultdict(set),
            'room': collections.defaultdict(set)
        }
        
        # Sort classes by priority (labs first, then high-credit subjects)
        classes = sorted(data['classes_to_schedule'], 
                        key=lambda x: (x.subject_type != 'Lab', -x.credits, random.random()))
        
        for class_info in classes:
            gene = self._create_gene(class_info, used_slots, data)
            if gene:
                chromosome.append(gene)
                used_slots['faculty'][gene.faculty_id].add((gene.day, gene.hour))
                used_slots['batch'][gene.batch_id].add((gene.day, gene.hour))
                used_slots['room'][gene.room_id].add((gene.day, gene.hour))
        
        return chromosome
    
    def calculate_fitness(self, chromosome: List[Gene]) -> float:
        """Enhanced fitness calculation with weighted constraints"""
        if not chromosome:
            return 0.0
        
        penalty = 0
        weights = {
            'hard_constraint': 1000,
            'consecutive_gap': 15,
            'excessive_consecutive': 25,
            'faculty_overload': 50,
            'room_preference': 5,
            'time_preference': 10
        }
        
        # Group by entities for constraint checking
        faculty_slots = collections.defaultdict(list)
        batch_slots = collections.defaultdict(list)
        room_slots = collections.defaultdict(list)
        
        for gene in chromosome:
            timeslot = (gene.day, gene.hour)
            faculty_slots[gene.faculty_id].append(timeslot)
            batch_slots[gene.batch_id].append(timeslot)
            room_slots[gene.room_id].append(timeslot)
        
        # Hard constraints (no double booking)
        for slots_dict in [faculty_slots, batch_slots, room_slots]:
            for entity_slots in slots_dict.values():
                unique_slots = set(entity_slots)
                if len(unique_slots) != len(entity_slots):
                    penalty += weights['hard_constraint'] * (len(entity_slots) - len(unique_slots))
        
        # Soft constraints for each batch
        for batch_id, slots in batch_slots.items():
            penalty += self._calculate_schedule_quality_penalty(slots, weights)
        
        # Faculty workload balance
        for faculty_id, slots in faculty_slots.items():
            hours_per_day = collections.defaultdict(int)
            for day, hour in slots:
                hours_per_day[day] += 1
            
            # Penalty for uneven daily distribution
            daily_hours = list(hours_per_day.values())
            if daily_hours:
                penalty += weights['faculty_overload'] * np.var(daily_hours)
        
        return 1 / (1 + penalty)
    
    def _calculate_schedule_quality_penalty(self, slots: List[Tuple[str, int]], 
                                          weights: Dict[str, int]) -> int:
        """Calculate penalty for schedule quality issues"""
        penalty = 0
        slots_by_day = collections.defaultdict(list)
        
        for day, hour in slots:
            slots_by_day[day].append(hour)
        
        for day, hours in slots_by_day.items():
            if len(hours) <= 1:
                continue
                
            hours = sorted(hours)
            
            # Penalty for gaps between classes
            for i in range(len(hours) - 1):
                gap = hours[i+1] - hours[i] - 1
                if gap > 1:  # More than 1-hour gap
                    penalty += weights['consecutive_gap'] * gap
            
            # Penalty for too many consecutive classes
            consecutive_count = 1
            max_consecutive = 0
            
            for i in range(len(hours) - 1):
                if hours[i+1] == hours[i] + 1:
                    consecutive_count += 1
                else:
                    max_consecutive = max(max_consecutive, consecutive_count)
                    consecutive_count = 1
            max_consecutive = max(max_consecutive, consecutive_count)
            
            if max_consecutive > settings.MAX_CONSECUTIVE_CLASSES:
                penalty += weights['excessive_consecutive'] * (max_consecutive - settings.MAX_CONSECUTIVE_CLASSES)
        
        return penalty
    
    def tournament_selection(self, population_fitness: List[Tuple[float, List[Gene]]]) -> List[Gene]:
        """Tournament selection for parent selection"""
        tournament_size = min(self.config.tournament_size, len(population_fitness))
        tournament = random.sample(population_fitness, tournament_size)
        return max(tournament, key=lambda x: x[0])[1]
    
    def crossover(self, parent1: List[Gene], parent2: List[Gene]) -> List[Gene]:
        """Enhanced crossover with repair mechanism"""
        if not parent1 or not parent2:
            return parent1 or parent2
        
        # Two-point crossover
        min_len = min(len(parent1), len(parent2))
        if min_len < 2:
            return parent1
        
        point1 = random.randint(1, min_len // 2)
        point2 = random.randint(min_len // 2, min_len - 1)
        
        child = parent1[:point1] + parent2[point1:point2] + parent1[point2:]
        
        # Repair conflicts
        child = self._repair_chromosome(child)
        
        return child
    
    def _repair_chromosome(self, chromosome: List[Gene]) -> List[Gene]:
        """Repair chromosome by removing conflicts"""
        if not chromosome:
            return chromosome
        
        seen_slots = {
            'faculty': collections.defaultdict(set),
            'batch': collections.defaultdict(set),
            'room': collections.defaultdict(set)
        }
        
        repaired = []
        
        for gene in chromosome:
            timeslot = (gene.day, gene.hour)
            
            # Check for conflicts
            if (timeslot in seen_slots['faculty'][gene.faculty_id] or
                timeslot in seen_slots['batch'][gene.batch_id] or
                timeslot in seen_slots['room'][gene.room_id]):
                continue  # Skip conflicting gene
            
            # Add to repaired chromosome
            repaired.append(gene)
            seen_slots['faculty'][gene.faculty_id].add(timeslot)
            seen_slots['batch'][gene.batch_id].add(timeslot)
            seen_slots['room'][gene.room_id].add(timeslot)
        
        return repaired
    
    def mutate(self, chromosome: List[Gene]) -> List[Gene]:
        """Enhanced mutation with multiple strategies"""
        if not chromosome or random.random() > self.config.mutation_rate:
            return chromosome
        
        mutated = chromosome.copy()
        
        # Different mutation strategies
        mutation_type = random.choice(['timeslot', 'swap', 'room'])
        
        if mutation_type == 'timeslot':
            # Change timeslot of random gene
            idx = random.randint(0, len(mutated) - 1)
            new_day = random.choice(settings.DAYS)
            new_hour = random.randint(1, settings.HOURS_PER_DAY)
            mutated[idx].day = new_day
            mutated[idx].hour = new_hour
            
        elif mutation_type == 'swap' and len(mutated) > 1:
            # Swap timeslots of two random genes
            idx1, idx2 = random.sample(range(len(mutated)), 2)
            mutated[idx1].day, mutated[idx2].day = mutated[idx2].day, mutated[idx1].day
            mutated[idx1].hour, mutated[idx2].hour = mutated[idx2].hour, mutated[idx1].hour
        
        # Repair after mutation
        mutated = self._repair_chromosome(mutated)
        
        return mutated
    
    def run_evolution(self, data: Dict, progress_callback=None, db: Session = None) -> List[Gene]:
        """Main evolution loop with progress tracking"""
        # Log optimization start
        if db:
            log_entry = OptimizationLog(
                run_id=self.run_id,
                operation_type='initial',
                status='running',
                parameters={
                    'population_size': self.config.population_size,
                    'max_generations': self.config.max_generations,
                    'mutation_rate': self.config.mutation_rate
                }
            )
            db.add(log_entry)
            db.commit()
            db.close()
        
        # Initialize population
        logger.info(f"Creating initial population of {self.config.population_size}")
        population = [self.create_chromosome(data) for _ in range(self.config.population_size)]
        
        best_fitness = 0
        best_chromosome = None
        generations_without_improvement = 0
        start_time = time.time()
        
        for generation in range(self.config.max_generations):
            # Calculate fitness for all chromosomes
            population_fitness = [(self.calculate_fitness(chromo), chromo) for chromo in population]
            population_fitness.sort(key=lambda x: x[0], reverse=True)
            
            current_best_fitness = population_fitness[0][0]
            self.fitness_history.append(current_best_fitness)
            
            if current_best_fitness > best_fitness:
                best_fitness = current_best_fitness
                best_chromosome = population_fitness[0][1].copy()
                generations_without_improvement = 0
            else:
                generations_without_improvement += 1
            
            # Progress callback
            if progress_callback:
                progress_callback(generation + 1, current_best_fitness)
            
            logger.info(f"Generation {generation + 1}/{self.config.max_generations} | "
                       f"Best Fitness: {current_best_fitness:.4f}")
            
            # Early stopping if optimal solution found
            if current_best_fitness >= 0.99:
                logger.info("Near-optimal solution found, stopping early")
                break
            
            # Adaptive parameters
            if generations_without_improvement > 20:
                self.config.mutation_rate = min(0.1, self.config.mutation_rate * 1.1)
            
            # Create next generation
            next_population = []
            
            # Elitism
            elite_count = int(self.config.population_size * self.config.elitism_rate)
            next_population.extend([chromo for _, chromo in population_fitness[:elite_count]])
            
            # Generate offspring
            while len(next_population) < self.config.population_size:
                parent1 = self.tournament_selection(population_fitness)
                parent2 = self.tournament_selection(population_fitness)
                child = self.crossover(parent1, parent2)
                child = self.mutate(child)
                next_population.append(child)
            
            population = next_population
        
        execution_time = time.time() - start_time
        
        # Update log
        if db:
            log_entry = db.query(OptimizationLog).filter(
                OptimizationLog.run_id == self.run_id
            ).first()
            if log_entry:
                log_entry.status = 'completed'
                log_entry.fitness_scores = self.fitness_history
                log_entry.execution_time = execution_time
                log_entry.completed_at = datetime.utcnow()
                db.commit()
        db.close()
        
        logger.info(f"Evolution completed in {execution_time:.2f} seconds")
        logger.info(f"Best fitness achieved: {best_fitness:.4f}")
        
        return best_chromosome or population_fitness[0][1]

class TimetableOptimizer:
    """High-level interface for timetable optimization"""
    
    def __init__(self):
        self.config = GAConfig()
    
    def generate_multiple_solutions(self, batches_df: pd.DataFrame, classrooms_df: pd.DataFrame,
                                  faculty_df: pd.DataFrame, subjects_df: pd.DataFrame,
                                  num_solutions: int = 3, db: Session = None) -> List[Tuple[List[Gene], float]]:
        """Generate multiple timetable solutions in parallel"""

        def run_single_ga(seed: int) -> Tuple[List[Gene], float]:
            random.seed(seed)
            np.random.seed(seed)

            ga = EnhancedTimetableGA(self.config)
            data = ga.prepare_data(batches_df, classrooms_df, faculty_df, subjects_df)
            best_chromosome = ga.run_evolution(data, db=db)
            fitness = ga.calculate_fitness(best_chromosome)

            return best_chromosome, fitness
        
        # Run multiple GA instances in parallel
        seeds = [random.randint(0, 10000) for _ in range(num_solutions)]
        
        with ThreadPoolExecutor(max_workers=min(num_solutions, 4)) as executor:
            results = list(executor.map(run_single_ga, seeds))
        
        # Sort by fitness
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
    
    def optimize_for_constraints(self, existing_timetable: List[Gene], 
                                constraints: Dict[str, Any]) -> List[Gene]:
        """Re-optimize timetable with additional constraints"""
        # Implementation for constraint-based re-optimization
        # This would be used for features like teacher leave, room changes, etc.
        pass
    
    def genes_to_dataframe(self, genes: List[Gene]) -> pd.DataFrame:
        """Convert genes to DataFrame for storage"""
        data = []
        for gene in genes:
            data.append({
                'batch_id': gene.batch_id,
                'subject_name': gene.subject_name,
                'faculty_id': gene.faculty_id,
                'room_id': gene.room_id,
                'day': gene.day,
                'hour': gene.hour,
                'week_type': gene.week_type
            })
        
        df = pd.DataFrame(data)
        return df.sort_values(['batch_id', 'day', 'hour'])