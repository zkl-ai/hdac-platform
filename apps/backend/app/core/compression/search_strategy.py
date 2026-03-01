import numpy as np
import copy
import json
import logging
import itertools
import hashlib

logger = logging.getLogger(__name__)

class EvolutionarySearch:
    def __init__(self, 
                 evaluator, 
                 pruner, 
                 population_size=10, 
                 num_generations=20, 
                 target_ratio=0.5,
                 initial_grid_rates=None,
                 log_callback=None,
                 abort_callback=None,
                 base_accuracy=None,
                 accuracy_constraint=None):
        self.evaluator = evaluator
        self.pruner = pruner
        self.population_size = population_size
        self.num_generations = num_generations
        self.target_ratio = target_ratio
        self.initial_grid_rates = initial_grid_rates # List of floats, e.g. [0.1, 0.2]
        self.log_callback = log_callback
        self.abort_callback = abort_callback
        self.base_accuracy = base_accuracy
        self.accuracy_constraint = accuracy_constraint

        self.layer_sizes = np.array(self.pruner.get_layer_sizes())
        self.num_genes = len(self.layer_sizes)
        
        self.fitness_cache = {}
        self.best_individual = None
        self.best_fitness = -float('inf')

    def _hash_individual(self, individual):
        return hashlib.sha256(individual.tobytes()).hexdigest()

    def _initialize_population(self):
        population = []
        
        # Strategy 1: Grid Initialization if rates provided
        if self.initial_grid_rates:
            # We want to cover the grid space.
            # If population size is large enough, we can sample from the grid.
            # Grid rates: e.g. [0.1, 0.2, 0.3]
            # Each gene (layer) can take one of these values.
            
            for _ in range(self.population_size):
                ind = np.random.choice(self.initial_grid_rates, size=self.num_genes)
                population.append(ind)
        else:
            # Strategy 2: Random initialization around target ratio
            # Random prune rate between 0 and 0.6 (Default fallback)
            for _ in range(self.population_size):
                ind = np.random.rand(self.num_genes) * 0.6
                population.append(ind)
        
        # Ensure we return valid numpy array
        if not population:
            # Fallback for empty population (should not happen given logic above)
            ind = np.random.rand(self.num_genes) * 0.6
            population.append(ind)
            
        return np.array(population)

    def _evaluate_fitness(self, individual):
        if individual is None:
            return -float('inf'), {}
            
        h = self._hash_individual(individual)
        if h in self.fitness_cache:
            return self.fitness_cache[h]

        # 1. Prune model (Temporary copy)
        # We need to prune to evaluate accuracy/latency accurately if using real evaluators.
        # Note: 'prune_by_rates' returns a NEW model copy.
        pruned_model = self.pruner.prune_by_rates(individual)
        
        # 2. Latency Evaluation
        # The evaluator might need the model OR just the rates (if using surrogate)
        # Our Evaluator interface supports both.
        latency_score = 1.0
        if 'latency' in self.evaluator:
             # LatencyEvaluator expects (model, prune_rate) usually, but Surrogate only needs rates.
             # RemoteEvaluator needs rates + model_name (handled internally).
             latency_score = self.evaluator['latency'].evaluate(pruned_model, individual)
        
        # 3. Accuracy Evaluation (Optional inside search loop?)
        # Running full inference on test set for EVERY individual in EVERY generation is slow.
        # Usually we use a "proxy" accuracy or just prune magnitude importance as a proxy?
        # Or run on a small subset of data.
        # For now, if 'accuracy' evaluator is present, we run it.
        acc_score = 1.0
        if 'accuracy' in self.evaluator:
            # Check if we should run it (maybe only for best candidates?)
            # For robustness, let's run it but warn it might be slow.
            acc_score = self.evaluator['accuracy'].evaluate(pruned_model)
            
        # Composite Fitness (Minimize Latency, Maximize Accuracy)
        # Objective: Minimize Latency subject to Accuracy > Threshold
        # Formula: if Acc(M') >= alpha * Acc(M), Cost = Obj
        # else, Cost = Obj + (1 - Acc(M')) / (1 - alpha)
        
        obj = latency_score
        cost = obj
        
        if self.accuracy_constraint is not None:
             limit = float(self.accuracy_constraint)
             if limit > 1.0: limit /= 100.0
             
             base = self.base_accuracy if self.base_accuracy else 0.8
             if base > 1e-6:
                alpha = (base - limit) / base
             else:
                alpha = 0.9
                
             threshold = alpha * base
             
             if acc_score < threshold:
                 denominator = 1.0 - alpha
                 if denominator < 1e-6: denominator = 1e-6
                 
                 penalty = (1.0 - acc_score) / denominator
                 cost += penalty
        
        score = -cost
        
        # Capture details for logging
        flops, params = self.pruner.get_flops_and_params(pruned_model)
        details = {
            'latency': latency_score,
            'flops': flops,
            'params': params,
            'accuracy': acc_score
        }
        
        self.fitness_cache[h] = (score, details)
        return score, details

    def search(self):
        """
        Run Evolutionary Search
        """
        logger.info("Starting Evolutionary Search...")
        population = self._initialize_population()
        
        best_solution = None
        max_score = -float('inf')
        
        # Ensure we always return something valid, even if loop doesn't run
        if population is not None and len(population) > 0:
            best_solution = population[0]
        else:
            best_solution = np.random.rand(self.num_genes) * 0.1

        best_details = {}

        for gen in range(self.num_generations):
            if self.abort_callback:
                self.abort_callback()
                
            # logger.info(f"Generation {gen+1}/{self.num_generations}")
            
            scores = []
            for i, ind in enumerate(population):
                score, details = self._evaluate_fitness(ind)
                scores.append(score)
                
                if score > max_score:
                    max_score = score
                    best_solution = ind
                    best_details = details
                    # logger.info(f"New best found: Score={score:.4f}")

            # Selection & Mutation
            # Tournament Selection
            new_pop = []
            new_pop.append(best_solution) # Elitism
            
            while len(new_pop) < self.population_size:
                # Tournament
                # Fix: Sample size cannot be larger than population size
                sample_size = min(3, len(population))
                candidates_idx = np.random.choice(len(population), sample_size, replace=False)
                candidates = population[candidates_idx]
                candidate_scores = [scores[i] for i in candidates_idx]
                winner = candidates[np.argmax(candidate_scores)]
                
                # Mutate
                if winner is None:
                    # Should not happen if initialization is correct
                    winner = np.random.rand(self.num_genes) * 0.6
                    
                child = winner + np.random.randn(self.num_genes) * 0.05
                child = np.clip(child, 0, 0.8)
                new_pop.append(child)
            
            population = np.array(new_pop)

            if self.log_callback:
                self.log_callback(gen+1, {
                    'best_score': float(max_score),
                    'avg_score': float(np.mean(scores)),
                    'best_latency': best_details.get('latency'),
                    'best_flops': best_details.get('flops'),
                    'best_accuracy': best_details.get('accuracy')
                })

        # If no best solution found (e.g. all evals failed), return random valid
        if best_solution is None:
            if population is not None and len(population) > 0:
                 best_solution = population[0]
            else:
                 best_solution = np.random.rand(self.num_genes) * 0.1 # Conservative fallback
                 
        return best_solution
