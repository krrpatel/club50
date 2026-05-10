"""Multi-language code templates for problems"""
from typing import Dict, Optional

# Two Sum templates
TWO_SUM_TEMPLATES: Dict[str, Dict[str, str]] = {
    "python": {
        "starter": '''def two_sum(nums: list[int], target: int) -> list[int]:
    """
    Find two numbers that add up to target.
    
    Args:
        nums: List of integers
        target: Target sum
    
    Returns:
        List of two indices [i, j] where nums[i] + nums[j] == target
    """
    # Your solution here
    pass
''',
        "solution": '''def two_sum(nums: list[int], target: int) -> list[int]:
    """Find two numbers that add up to target"""
    seen = {}
    for i, num in enumerate(nums):
        complement = target - num
        if complement in seen:
            return [seen[complement], i]
        seen[num] = i
    return []
''',
    },
    "javascript": {
        "starter": '''function twoSum(nums, target) {
    /**
     * Find two numbers that add up to target.
     * @param {number[]} nums - Array of integers
     * @param {number} target - Target sum
     * @returns {number[]} - Array of two indices [i, j]
     */
    // Your solution here
}

// Test
console.log(twoSum([2, 7, 11, 15], 9)); // [0, 1]
''',
        "solution": '''function twoSum(nums, target) {
    const seen = {};
    for (let i = 0; i < nums.length; i++) {
        const complement = target - nums[i];
        if (complement in seen) {
            return [seen[complement], i];
        }
        seen[nums[i]] = i;
    }
    return [];
}
''',
    },
    "java": {
        "starter": '''public class Solution {
    /**
     * Find two numbers that add up to target.
     * @param nums Array of integers
     * @param target Target sum
     * @return Array of two indices [i, j]
     */
    public static int[] twoSum(int[] nums, int target) {
        // Your solution here
        return new int[0];
    }
    
    public static void main(String[] args) {
        int[] result = twoSum(new int[]{2, 7, 11, 15}, 9);
        System.out.println(Arrays.toString(result)); // [0, 1]
    }
}
''',
        "solution": '''import java.util.HashMap;
import java.util.Map;

public class Solution {
    public static int[] twoSum(int[] nums, int target) {
        Map<Integer, Integer> seen = new HashMap<>();
        for (int i = 0; i < nums.length; i++) {
            int complement = target - nums[i];
            if (seen.containsKey(complement)) {
                return new int[]{seen.get(complement), i};
            }
            seen.put(nums[i], i);
        }
        return new int[0];
    }
}
''',
    },
    "cpp": {
        "starter": '''#include <vector>
#include <unordered_map>
using namespace std;

/**
 * Find two numbers that add up to target.
 * @param nums Vector of integers
 * @param target Target sum
 * @return Vector of two indices [i, j]
 */
vector<int> twoSum(vector<int>& nums, int target) {
    // Your solution here
    return {};
}

int main() {
    vector<int> nums = {2, 7, 11, 15};
    vector<int> result = twoSum(nums, 9);
    // [0, 1]
    return 0;
}
''',
        "solution": '''#include <vector>
#include <unordered_map>
using namespace std;

vector<int> twoSum(vector<int>& nums, int target) {
    unordered_map<int, int> seen;
    for (int i = 0; i < nums.size(); i++) {
        int complement = target - nums[i];
        if (seen.find(complement) != seen.end()) {
            return {seen[complement], i};
        }
        seen[nums[i]] = i;
    }
    return {};
}
''',
    },
}


class TemplateManager:
    """Manage code templates for problems"""
    
    # Problem templates database
    TEMPLATES = {
        "two_sum": TWO_SUM_TEMPLATES,
        # TODO: Add more problem templates
    }
    
    @classmethod
    def get_starter_template(cls, problem_slug: str, language: str) -> Optional[str]:
        """Get starter code template for a problem and language"""
        if problem_slug not in cls.TEMPLATES:
            return None
        
        templates = cls.TEMPLATES[problem_slug]
        if language not in templates:
            return None
        
        return templates[language].get("starter")
    
    @classmethod
    def get_solution_template(cls, problem_slug: str, language: str) -> Optional[str]:
        """Get solution code template for a problem and language"""
        if problem_slug not in cls.TEMPLATES:
            return None
        
        templates = cls.TEMPLATES[problem_slug]
        if language not in templates:
            return None
        
        return templates[language].get("solution")
    
    @classmethod
    def get_all_templates(cls, problem_slug: str) -> Optional[Dict[str, Dict[str, str]]]:
        """Get all templates for a problem"""
        return cls.TEMPLATES.get(problem_slug)
    
    @classmethod
    def get_supported_languages(cls, problem_slug: str) -> list[str]:
        """Get list of supported languages for a problem"""
        if problem_slug not in cls.TEMPLATES:
            return []
        
        return list(cls.TEMPLATES[problem_slug].keys())


# Function signatures for problems
FUNCTION_SIGNATURES: Dict[str, Dict[str, str]] = {
    "two_sum": {
        "python": "def two_sum(nums: list[int], target: int) -> list[int]:",
        "javascript": "function twoSum(nums, target)",
        "java": "public static int[] twoSum(int[] nums, int target)",
        "cpp": "vector<int> twoSum(vector<int>& nums, int target)",
    },
    # TODO: Add more function signatures
}


def get_function_signature(problem_slug: str, language: str) -> Optional[str]:
    """Get function signature for a problem"""
    if problem_slug not in FUNCTION_SIGNATURES:
        return None
    
    return FUNCTION_SIGNATURES[problem_slug].get(language)


# Example I/O for problems
PROBLEM_EXAMPLES: Dict[str, list[Dict]] = {
    "two_sum": [
        {
            "input": {"nums": [2, 7, 11, 15], "target": 9},
            "output": [0, 1],
            "explanation": "nums[0] + nums[1] = 2 + 7 = 9"
        },
        {
            "input": {"nums": [3, 2, 4], "target": 6},
            "output": [1, 2],
            "explanation": "nums[1] + nums[2] = 2 + 4 = 6"
        },
        {
            "input": {"nums": [3, 3], "target": 6},
            "output": [0, 1],
            "explanation": "nums[0] + nums[1] = 3 + 3 = 6"
        },
    ],
}


def get_problem_examples(problem_slug: str) -> list[Dict]:
    """Get example test cases for a problem"""
    return PROBLEM_EXAMPLES.get(problem_slug, [])
